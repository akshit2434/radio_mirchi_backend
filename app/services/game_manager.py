import asyncio
import json
from enum import Enum, auto
from fastapi import WebSocket
from typing import Dict, List, Optional
from app.services.llm_service import generate_dialogue
from app.services.deepgram_service import deepgram_service
from app.db.propaganda_db import get_propaganda_mission_by_id
from app.db.mongodb_utils import get_database
from app.schemas.propaganda import DialogueLine, Speaker

class ConnectionManager:
    """Manages active WebSocket connections."""
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, mission_id: str):
        await websocket.accept()
        self.active_connections[mission_id] = websocket

    def disconnect(self, mission_id: str):
        if mission_id in self.active_connections:
            del self.active_connections[mission_id]

    async def send_to_client(self, message: str, mission_id: str):
        if mission_id in self.active_connections:
            await self.active_connections[mission_id].send_text(message)

class SessionState(Enum):
    IDLE = auto()
    SPEAKING_TTS = auto()
    LISTENING_TO_USER = auto()

class GameSession:
    """
    Manages the game state and dialogue flow with a robust state machine
    to prevent race conditions and overlapping audio.
    """
    def __init__(self, mission_id: str, manager: ConnectionManager):
        self.mission_id = mission_id
        self.manager = manager
        self.dialogue_queue: asyncio.Queue[DialogueLine] = asyncio.Queue()
        self.speakers: List[Speaker] = []
        self.dialogue_history = ""
        self.mission_context = ""
        self.proof_sentences: List[str] = []
        self.initial_listeners: int = 0 # New: Store initial listeners
        self._awakened_listeners: float = 0.0 # New: Track awakened listeners
        
        self._is_active = True
        self._state = SessionState.IDLE
        self._state_lock = asyncio.Lock()
        
        self._main_task: Optional[asyncio.Task] = None
        self._tts_task: Optional[asyncio.Task] = None
        self._listener_broadcast_task: Optional[asyncio.Task] = None # New: Task for broadcasting listeners
        
        self._live_transcriber = deepgram_service.get_live_transcriber()

    async def start(self):
        print(f"Game session starting for mission {self.mission_id}")
        db = await get_database()
        mission = await get_propaganda_mission_by_id(self.mission_id, db)
        if not mission or not mission.dialogue_generator_prompt:
            await self.manager.send_to_client(json.dumps({"error": "Mission not ready."}), self.mission_id)
            return
        
        self.speakers = mission.generation_result.speakers
        self.mission_context = mission.dialogue_generator_prompt
        self.proof_sentences = mission.generation_result.proof_sentences
        self.initial_listeners = mission.generation_result.initial_listeners # New: Set initial listeners
        self._awakened_listeners = 0.0 # Initialize awakened listeners to 0 at start
        
        self._main_task = asyncio.create_task(self._main_loop())
        self._listener_broadcast_task = asyncio.create_task(self._broadcast_listeners_loop()) # New: Start broadcast task

    async def stop(self):
        print(f"Stopping game session for mission {self.mission_id}")
        self._is_active = False
        
        tasks_to_cancel = [self._main_task, self._tts_task, self._listener_broadcast_task] # New: Add broadcast task to cancel list
        for task in tasks_to_cancel:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        if self._live_transcriber._is_active:
            await self._live_transcriber.stop()
            
        print("Game session tasks cancelled successfully.")

    async def signal_ready_for_next(self):
        """Triggers the next action in the main loop if the session is idle."""
        pass # Main loop is now continuous, no need to trigger it here

    async def start_user_speech(self):
        """Transitions the state to listening, cancelling any ongoing TTS."""
        async with self._state_lock:
            if self._state == SessionState.SPEAKING_TTS and self._tts_task:
                self._tts_task.cancel()
            
            self._state = SessionState.LISTENING_TO_USER
            print("[GameSession] State changed to LISTENING_TO_USER")
            
            while not self.dialogue_queue.empty():
                self.dialogue_queue.get_nowait()
            print("[GameSession] Dialogue queue cleared for user speech.")

        await self._live_transcriber.start()

    async def stop_user_speech(self):
        """
        Stops the transcriber, processes the final transcript, and triggers the next
        dialogue generation. This is the single point of truth for ending user speech.
        """
        print("[GameSession] User speech stopped.")
        if not self._live_transcriber._is_active:
            return

        transcript = await self._live_transcriber.stop()
        
        async with self._state_lock:
            if transcript:
                print(f"[GameSession] Final transcript processed: '{transcript}'")
                self.dialogue_history += f"\nUser: {transcript}"
            
            self._state = SessionState.IDLE
            print("[GameSession] State changed to IDLE")
        
        # The continuous _main_loop will pick up from here

    async def handle_user_dialogue(self, dialogue: str):
        """
        Handles incoming user dialogue, interrupts current TTS, clears the queue,
        and appends the user's message to the history to influence the next generation.
        """
        print(f"[GameSession] Handling user dialogue: '{dialogue}'")
        async with self._state_lock:
            if self._state == SessionState.SPEAKING_TTS and self._tts_task:
                self._tts_task.cancel()
                print("[GameSession] Cancelled running TTS task due to user dialogue.")

            # Clear any pending dialogue
            while not self.dialogue_queue.empty():
                self.dialogue_queue.get_nowait()
            print("[GameSession] Dialogue queue cleared.")

            # Append user dialogue to history
            self.dialogue_history += f"\nUser: {dialogue}"
            
            # Set state to IDLE, the main loop will now generate new dialogue
            self._state = SessionState.IDLE
            print("[GameSession] State set to IDLE to trigger new dialogue generation.")

    async def _stream_tts_for_line(self, dialogue_line: DialogueLine):
        """Streams TTS for a single line. This is a self-contained task."""
        try:

            speaker_name = dialogue_line.speaker_name
            line_text = dialogue_line.line
            print(f"[GameSession] Speaking ({speaker_name}): {line_text}")
            
            speaker_gender = next((s.gender for s in self.speakers if s.name == speaker_name), "female")
            
            tts_stream = deepgram_service.text_to_speech_stream(line_text, speaker_gender)
            async for chunk in tts_stream:
                await self.manager.active_connections[self.mission_id].send_bytes(chunk)
            
            self.dialogue_history += f"\n{speaker_name}: {line_text}"
            print(f"[GameSession] Finished streaming TTS for line: '{line_text}'")
            

        except asyncio.CancelledError:
            print(f"[GameSession] TTS for '{dialogue_line.line[:30]}...' was cancelled.")
        except Exception as e:
            print(f"Error during TTS streaming: {e}")
        finally:
            self.dialogue_queue.task_done()

    async def _main_loop(self):
        """
        The core logic loop. It continuously processes dialogue and manages TTS playback sequentially.
        """
        while self._is_active:
            if self._state == SessionState.IDLE:
                if self.dialogue_queue.empty():
                    # If idle and queue is empty, generate new dialogue.
                    print("[GameSession] Dialogue queue empty. Generating new batch...")
                    # Temporarily block state during generation.
                    async with self._state_lock:
                        self._state = SessionState.SPEAKING_TTS
                    
                    new_dialogues = await asyncio.to_thread(
                        generate_dialogue, self.mission_context, self.dialogue_history, self.proof_sentences
                    )
                    
                    if new_dialogues:
                        print(f"[GameSession] Generated dialogue batch size: {len(new_dialogues)}")
                        for dialogue in new_dialogues:
                            await self.dialogue_queue.put(dialogue)
                    else:
                        print("[GameSession] Failed to generate new dialogues.")
                    
                    # Revert to IDLE to allow the loop to pick up the new dialogue.
                    async with self._state_lock:
                        self._state = SessionState.IDLE
                else:
                    # If idle and queue has items, speak the next line.
                    async with self._state_lock:
                        self._state = SessionState.SPEAKING_TTS
                    
                    dialogue_line = await self.dialogue_queue.get()
                    self._tts_task = asyncio.create_task(self._stream_tts_for_line(dialogue_line))
                    
                    try:
                        # Await the task to ensure sequential playback.
                        await self._tts_task
                    except asyncio.CancelledError:
                        # If cancelled, the cancelling function is responsible for the state change.
                        print("[GameSession] TTS task was externally cancelled.")
                    else:
                        # If it finished normally, revert to IDLE for the next line.
                        async with self._state_lock:
                            self._state = SessionState.IDLE
            
            # Wait a bit before the next check to prevent busy-waiting.
            await asyncio.sleep(0.1)

    async def _broadcast_listeners_loop(self):
        """Periodically sends the current awakened listener count to the client."""
        while self._is_active:
            try:
                # Clamp awakened listeners between 0 and initial_listeners
                clamped_listeners = max(0, min(self.initial_listeners, int(self._awakened_listeners)))
                
                message = json.dumps({"awakened_listeners": clamped_listeners})
                await self.manager.send_to_client(message, self.mission_id)
                print(f"[GameSession] Sent awakened listeners: {clamped_listeners}")
            except Exception as e:
                print(f"Error broadcasting listeners: {e}")
            
            await asyncio.sleep(1) # Send every second

# A dictionary to hold active game sessions
game_sessions: Dict[str, GameSession] = {}

# Singleton instance of the connection manager
manager = ConnectionManager()