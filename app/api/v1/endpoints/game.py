from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import json
from app.services.game_manager import manager, GameSession, game_sessions

router = APIRouter()

@router.websocket("/ws/{mission_id}")
async def websocket_endpoint(websocket: WebSocket, mission_id: str):
    await manager.connect(websocket, mission_id)
    session: GameSession | None = None
    try:
        if mission_id not in game_sessions:
            session = GameSession(mission_id, manager)
            game_sessions[mission_id] = session
            await session.start()
        else:
            session = game_sessions[mission_id]

        while True:
            message = await websocket.receive()
            
            if "text" in message:
                data = json.loads(message["text"])
                action = data.get("action")
                
                if action == "ready_for_next":
                    print(f"Received 'ready_for_next' from client for mission {mission_id}")
                    if session:
                        await session.signal_ready_for_next()
                elif action == "start_speech":
                    print(f"Received 'start_speech' from client for mission {mission_id}")
                    if session:
                        await session.start_user_speech()
                elif action == "stop_speech":
                    print(f"Received 'stop_speech' from client for mission {mission_id}")
                    if session:
                        await session.stop_user_speech()

                elif action == "user_dialogue":
                    dialogue_text = data.get("dialogue")
                    if session and dialogue_text:
                        print(f"Received 'user_dialogue' from client for mission {mission_id}")
                        await session.handle_user_dialogue(dialogue_text)

    except WebSocketDisconnect:
        print(f"Client disconnected from mission {mission_id}. Cleaning up session.")
        if mission_id in game_sessions:
            session = game_sessions[mission_id]
            await session.stop()
            del game_sessions[mission_id]
        
        manager.disconnect(mission_id)
        print(f"Session for mission {mission_id} closed.")