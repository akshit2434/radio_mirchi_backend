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
        self._generation_task: Optional[asyncio.Task] = None

    async def start(self):
        """Initializes and starts the game session and its dialogue generation loop."""
        print(f"Game session starting for mission {self.mission_id}")
        db = await get_database()
        mission = await get_propaganda_mission_by_id(self.mission_id, db)
        if not mission or not mission.dialogue_generator_prompt:
            await self.manager.send_to_client("Error: Mission not ready.", self.mission_id)
            return
        
        self.speakers = mission.generation_result.speakers
        self.mission_context = mission.dialogue_generator_prompt
        
        # Start the dialogue generation and speaking loop
        self._generation_task = asyncio.create_task(self.run_dialogue_loop())

    async def stop(self):
        """Stops the game session and cleans up resources."""
        print(f"Stopping game session for mission {self.mission_id}")
        self._is_active = False
        if self._generation_task:
            self._generation_task.cancel()
            try:
                await self._generation_task
            except asyncio.CancelledError:
                print("Dialogue generation task cancelled successfully.")

    async def _populate_dialogue_queue(self):
        """Generates new dialogue and adds it to the queue."""
        print("Generating new dialogue...")
        try:
            new_dialogues = generate_dialogue(self.mission_context, self.dialogue_history)
            for dialogue in new_dialogues:
                await self.dialogue_queue.put(dialogue)
                # Update history for the next generation cycle
                self.dialogue_history += f"\n{dialogue.speaker_name}: {dialogue.line}"
        except Exception as e:
            print(f"Error generating dialogue: {e}")

    async def run_dialogue_loop(self):
        """The main loop that generates and speaks dialogue continuously."""
        await self._populate_dialogue_queue() # Initial population

        while self._is_active:
            try:
                # If queue is low, fetch more dialogue
                if self.dialogue_queue.qsize() < 2:
                    await self._populate_dialogue_queue()

                dialogue_line = await self.dialogue_queue.get()
                
                speaker_name = dialogue_line.speaker_name
                line_text = dialogue_line.line
                
                print(f"Speaking ({speaker_name}): {line_text}")
                
                speaker_gender = next((s.gender for s in self.speakers if s.name == speaker_name), "female")
                
                # Stream the audio to the client
                tts_stream = deepgram_service.text_to_speech_stream(line_text, speaker_gender)
                async for chunk in tts_stream:
                    print(f"[GameSession] Received audio chunk from Deepgram: {len(chunk)} bytes, head={chunk[:8].hex() if isinstance(chunk, bytes) else 'N/A'}")
                    if self.mission_id in self.manager.active_connections:
                        print(f"[GameSession] Sending audio chunk: {len(chunk)} bytes to client {self.mission_id}, head={chunk[:8].hex() if isinstance(chunk, bytes) else 'N/A'}")
                        await self.manager.active_connections[self.mission_id].send_bytes(chunk)
                    else:
                        print("Client disconnected mid-stream. Stopping session.")
                        await self.stop()
                        break
                print(f"[GameSession] Finished streaming TTS for line: '{line_text}'")
                
                self.dialogue_queue.task_done()

            except asyncio.CancelledError:
                break # Exit loop if task is cancelled
            except Exception as e:
                print(f"Error in dialogue loop: {e}")
                await asyncio.sleep(5) # Wait before retrying on error

# A dictionary to hold active game sessions
game_sessions: Dict[UUID, GameSession] = {}

# Singleton instance of the connection manager
manager = ConnectionManager()