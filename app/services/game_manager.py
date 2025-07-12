import asyncio
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
    Encapsulates the state and logic for a single mission's game session,
    creating a continuous dialogue stream.
    """
    def __init__(self, mission_id: UUID, manager: ConnectionManager):
        self.mission_id = mission_id
        self.manager = manager
        self.dialogue_queue: asyncio.Queue[DialogueLine] = asyncio.Queue()
        self.speakers: List[Speaker] = []
        self.dialogue_history = ""
        self.mission_context = ""
        self._is_active = True
        self._speaker_task: Optional[asyncio.Task] = None
        self._writer_task: Optional[asyncio.Task] = None

    async def start(self):
        """Initializes and starts the concurrent dialogue generation and speaking tasks."""
        print(f"Game session starting for mission {self.mission_id}")
        db = await get_database()
        mission = await get_propaganda_mission_by_id(self.mission_id, db)
        if not mission or not mission.dialogue_generator_prompt:
            await self.manager.send_to_client("Error: Mission not ready.", self.mission_id)
            return
        
        self.speakers = mission.generation_result.speakers
        self.mission_context = mission.dialogue_generator_prompt
        
        # Start the concurrent "writer" (dialogue generation) and "speaker" (TTS) tasks
        self._writer_task = asyncio.create_task(self._continuous_dialogue_generation_loop())
        self._speaker_task = asyncio.create_task(self._speaking_loop())

    async def stop(self):
        """Stops the game session and cleans up all running tasks."""
        print(f"Stopping game session for mission {self.mission_id}")
        self._is_active = False
        for task in [self._writer_task, self._speaker_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass # Expected on cancellation
        print("All game session tasks cancelled successfully.")

    async def _continuous_dialogue_generation_loop(self):
        """A background task that continuously generates dialogue to keep the queue filled."""
        while self._is_active:
            try:
                # Maintain a buffer of at least 5 lines
                if self.dialogue_queue.qsize() < 5:
                    print("[GameSession] Generating new batch of dialogue...")
                    new_dialogues = await asyncio.to_thread(generate_dialogue, self.mission_context, self.dialogue_history)
                    print(f"[GameSession] Dialogue batch size: {len(new_dialogues)}")
                    for dialogue in new_dialogues:
                        # Update history for the *next* generation cycle
                        self.dialogue_history += f"\n{dialogue.speaker_name}: {dialogue.line}"
                        await self.dialogue_queue.put(dialogue)
                # Wait a bit before checking again to avoid busy-waiting
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                print("Dialogue generation loop cancelled.")
                break
            except Exception as e:
                print(f"Error in dialogue generation loop: {e}")
                await asyncio.sleep(5) # Wait longer on error

    async def _speaking_loop(self):
        """The main loop that pulls dialogue from the queue and streams it as audio."""
        while self._is_active:
            try:
                # This will wait until a dialogue line is available
                dialogue_line = await self.dialogue_queue.get()
                
                speaker_name = dialogue_line.speaker_name
                line_text = dialogue_line.line
                
                print(f"[GameSession] Speaking ({speaker_name}): {line_text}")
                
                speaker_gender = next((s.gender for s in self.speakers if s.name == speaker_name), "female")
                
                # Stream the audio to the client
                tts_stream = deepgram_service.text_to_speech_stream(line_text, speaker_gender)
                async for chunk in tts_stream:
                    if self.mission_id in self.manager.active_connections:
                        await self.manager.active_connections[self.mission_id].send_bytes(chunk)
                    else:
                        print("Client disconnected mid-stream. Stopping session.")
                        await self.stop()
                        return # Exit the loop completely
                
                print(f"[GameSession] Finished streaming TTS for line: '{line_text}'")
                self.dialogue_queue.task_done()

            except asyncio.CancelledError:
                print("Speaking loop cancelled.")
                break
            except Exception as e:
                print(f"Error in speaking loop: {e}")
                await asyncio.sleep(1)

# A dictionary to hold active game sessions
game_sessions: Dict[UUID, GameSession] = {}

# Singleton instance of the connection manager
manager = ConnectionManager()