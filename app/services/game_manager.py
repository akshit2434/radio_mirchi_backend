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
        self._is_active = True
        self._main_task: Optional[asyncio.Task] = None

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

    async def _dialogue_and_speaking_loop(self):
        """
        Main loop that generates dialogue and streams it sequentially.
        It ensures a new dialogue batch is only generated after the previous one
        has been completely streamed to the client.
        """
        while self._is_active:
            try:
                if self.dialogue_queue.empty():
                    print("[GameSession] Dialogue queue empty. Generating new batch...")
                    new_dialogues = await asyncio.to_thread(
                        generate_dialogue, self.mission_context, self.dialogue_history
                    )
                    print(f"[GameSession] Generated dialogue batch size: {len(new_dialogues)}")
                    
                    if not new_dialogues:
                        await asyncio.sleep(5) # Avoid busy-loop if generation fails
                        continue
                        
                    for dialogue in new_dialogues:
                        self.dialogue_history += f"\n{dialogue.speaker_name}: {dialogue.line}"
                        await self.dialogue_queue.put(dialogue)

                # Get the next line from the queue. This will wait if the queue is
                # currently empty but a generation task is running.
                dialogue_line = await self.dialogue_queue.get()
                
                speaker_name = dialogue_line.speaker_name
                line_text = dialogue_line.line
                
                print(f"[GameSession] Speaking ({speaker_name}): {line_text}")
                
                speaker_gender = next((s.gender for s in self.speakers if s.name == speaker_name), "female")
                
                # Stream the audio to the client. This block ensures that if the
                # client disconnects at any point, the session is stopped gracefully.
                try:
                    tts_stream = deepgram_service.text_to_speech_stream(line_text, speaker_gender)
                    async for chunk in tts_stream:
                        # This send operation will raise an exception if the client has disconnected.
                        await self.manager.active_connections[self.mission_id].send_bytes(chunk)
                    
                    print(f"[GameSession] Finished streaming TTS for line: '{line_text}'")
                    self.dialogue_queue.task_done()

                except Exception as e:
                    # This block catches errors during TTS or sending, which are often
                    # caused by client disconnections (e.g., KeyError, RuntimeError).
                    print(f"Error during streaming for mission {self.mission_id}: {e}. Stopping session.")
                    await self.stop()
                    return # Exit the task completely

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