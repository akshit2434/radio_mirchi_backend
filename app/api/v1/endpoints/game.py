from fastapi import APIRouter, WebSocket, WebSocketDisconnect
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

        # Keep the connection alive, listening for the client to disconnect.
        while True:
            await websocket.receive_text() # This will block until the connection is closed.
            
    except WebSocketDisconnect:
        print(f"Client disconnected from mission {mission_id}. Cleaning up session.")
        if session:
            await session.stop()
        
        manager.disconnect(mission_id)
        if mission_id in game_sessions:
            del game_sessions[mission_id]
        
        print(f"Session for mission {mission_id} closed.")