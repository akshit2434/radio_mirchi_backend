from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import json
from uuid import UUID
from app.services.game_manager import manager, GameSession, game_sessions

router = APIRouter()

@router.websocket("/ws/{mission_id}")
async def websocket_endpoint(websocket: WebSocket, mission_id: UUID):
    await manager.connect(websocket, mission_id)
    session = None
    try:
        # Create and start a new game session if one doesn't exist
        if mission_id not in game_sessions:
            session = GameSession(mission_id, manager)
            game_sessions[mission_id] = session
            await session.start()
        else:
            session = game_sessions[mission_id]

        # Listen for messages from the client.
        while True:
            message = await websocket.receive_text()
            data = json.loads(message)
            
            if data.get("action") == "ready_for_next":
                print(f"Received 'ready_for_next' from client for mission {mission_id}")
                if session:
                    session.signal_ready_for_next()
            
    except WebSocketDisconnect:
        print(f"Client disconnected from mission {mission_id}. Cleaning up session.")
        if session:
            await session.stop()
        
        manager.disconnect(mission_id)
        if mission_id in game_sessions:
            del game_sessions[mission_id]
        
        print(f"Session for mission {mission_id} closed.")