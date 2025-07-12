import asyncio
import json
from fastapi import WebSocket
from uuid import UUID
from typing import Dict, List, Optional
from app.services.llm_service import generate_dialogue
from app.services.deepgram_service import deepgram_service
from app.db.propaganda_db import get_propaganda_mission_by_id
from app.db.mongodb_utils import get_database
from app.schemas.propaganda import DialogueLine, Speaker

class ConnectionManager:
    """Manages active WebSocket connections."""
    def __init__(self):
        self.active_connections: Dict[UUID, WebSocket] = {}

    async def connect(self, websocket: WebSocket, mission_id: UUID):
        await websocket.accept()
        self.active_connections[mission_id] = websocket

    def disconnect(self, mission_id: UUID):
        if mission_id in self.active_connections:
            del self.active_connections[mission_id]

    async def send_to_client(self, message: str, mission_id: UUID):
        if mission_id in self.active_connections:
            await self.active_connections[mission_id].send_text(message)

class GameSession:
    """
    Encapsulates the state and logic for a single mission's game session.
    It creates a continuous, sequential dialogue stream by generating dialogue
    only when the previous batch has been fully streamed.
    """
    def __init__(self, mission_id: UUID, manager: ConnectionManager):
        self.mission_id = mission_id
        self.manager = manager
        self.dialogue_queue: asyncio.Queue[DialogueLine] = asyncio.Queue()
        self.speakers: List[Speaker] = []
        self.dialogue_history = ""
        self.mission_context = ""
        self.proof_sentences: List[str] = []
        self._is_active = True
        self._main_task: Optional[asyncio.Task] = None
        self._ready_for_next = asyncio.Event()

    async def start(self):
        """Initializes and starts the main dialogue and speaking loop."""
        print(f"Game session starting for mission {self.mission_id}")
        db = await get_database()
        mission = await get_propaganda_mission_by_id(self.mission_id, db)
        if not mission or not mission.dialogue_generator_prompt:
            await self.manager.send_to_client("Error: Mission not ready.", self.mission_id)
            return
        
        self.speakers = mission.generation_result.speakers
        self.mission_context = mission.dialogue_generator_prompt
        self.proof_sentences = mission.generation_result.proof_sentences
        
        self._ready_for_next.set() # Allow the first dialogue to start immediately
        self._main_task = asyncio.create_task(self._dialogue_and_speaking_loop())

    async def stop(self):
        """Stops the game session and cleans up the main task."""
        print(f"Stopping game session for mission {self.mission_id}")
        self._is_active = False
        if self._main_task:
            self._main_task.cancel()
            try:
                await self._main_task
            except asyncio.CancelledError:
                pass # Expected on cancellation
        print("Game session task cancelled successfully.")

    def signal_ready_for_next(self):
        """Signals that the client is ready for the next dialogue."""
        if not self._ready_for_next.is_set():
            print(f"[GameSession] Client is ready. Signalling for next dialogue.")
            self._ready_for_next.set()

    async def _dialogue_and_speaking_loop(self):
        """
        Main loop that generates dialogue and streams it sequentially.
        It waits for a signal from the client before starting the next dialogue.
        """
        while self._is_active:
            try:
                # Wait for the client to be ready before processing the next dialogue.
                await self._ready_for_next.wait()
                self._ready_for_next.clear() # Reset for the next wait cycle.

                if self.dialogue_queue.empty():
                    print("[GameSession] Dialogue queue empty. Generating new batch...")
                    new_dialogues = await asyncio.to_thread(
                        generate_dialogue, self.mission_context, self.dialogue_history, self.proof_sentences
                    )
                    print(f"[GameSession] Generated dialogue batch size: {len(new_dialogues)}")
                    
                    if not new_dialogues:
                        await asyncio.sleep(5)
                        self._ready_for_next.set() # Re-set if generation fails to avoid deadlock
                        continue
                        
                    for dialogue in new_dialogues:
                        self.dialogue_history += f"\n{dialogue.speaker_name}: {dialogue.line}"
                        await self.dialogue_queue.put(dialogue)

                dialogue_line = await self.dialogue_queue.get()
                
                speaker_name = dialogue_line.speaker_name
                line_text = dialogue_line.line
                
                print(f"[GameSession] Speaking ({speaker_name}): {line_text}")
                
                speaker_gender = next((s.gender for s in self.speakers if s.name == speaker_name), "female")
                
                try:
                    tts_stream = deepgram_service.text_to_speech_stream(line_text, speaker_gender)
                    async for chunk in tts_stream:
                        await self.manager.active_connections[self.mission_id].send_bytes(chunk)
                    
                    print(f"[GameSession] Finished streaming TTS for line: '{line_text}'")
                    
                    # Signal to the client that this dialogue is finished.
                    end_of_dialogue_signal = json.dumps({"status": "dialogue_end"})
                    await self.manager.active_connections[self.mission_id].send_text(end_of_dialogue_signal)
                    print("[GameSession] Sent end-of-dialogue signal.")

                    self.dialogue_queue.task_done()

                except Exception as e:
                    print(f"Error during streaming for mission {self.mission_id}: {e}. Stopping session.")
                    await self.stop()
                    return

            except asyncio.CancelledError:
                print("Dialogue and speaking loop cancelled.")
                break
            except Exception as e:
                print(f"An unexpected error occurred in the main loop: {e}")
                await asyncio.sleep(1)

# A dictionary to hold active game sessions
game_sessions: Dict[UUID, GameSession] = {}

# Singleton instance of the connection manager
manager = ConnectionManager()