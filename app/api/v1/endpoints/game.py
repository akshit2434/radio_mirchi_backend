from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from uuid import UUID

router = APIRouter()

@router.websocket("/ws/{mission_id}")
async def websocket_endpoint(websocket: WebSocket, mission_id: UUID):
    await websocket.accept()
    try:
        while True:
            # This is a basic structure. We will add the game logic here.
            # For now, it can just wait for messages or be a placeholder.
            data = await websocket.receive_text()
            await websocket.send_text(f"Message text was: {data}, for mission {mission_id}")
    except WebSocketDisconnect:
        print(f"Client disconnected from mission {mission_id}")