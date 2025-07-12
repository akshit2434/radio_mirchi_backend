import asyncio
import json
import sys
import numpy as np
import sounddevice as sd
import websockets
import aiohttp

BASE_URL = "http://localhost:8000/api/v1"
mission_data_storage = {}
SAMPLE_RATE = 24000  # The sample rate for Deepgram's Aura TTS models

def pretty_print_json(data):
    """Prints JSON data in a readable format."""
    print(json.dumps(data, indent=4))

async def create_mission(session: aiohttp.ClientSession):
    """Calls the create_mission endpoint asynchronously and stores the mission data."""
    topic = input("Enter the mission topic: ")
    user_id = input("Enter your user ID: ")
    
    print("\nCreating mission...")
    try:
        async with session.post(
            f"{BASE_URL}/create_mission", 
            json={"topic": topic, "user_id": user_id}
        ) as response:
            response.raise_for_status()
            
            mission_data = await response.json()
            mission_id = mission_data.get("id")
            
            if mission_id:
                mission_data_storage['current_mission'] = mission_data
                print("Mission created successfully!")
                pretty_print_json(mission_data)
            else:
                print("Error: Mission ID not found in the response.")
                pretty_print_json(mission_data)
                
    except aiohttp.ClientError as e:
        print(f"An error occurred: {e}")

async def poll_and_connect(session: aiohttp.ClientSession):
    """Polls for mission status and connects to the WebSocket to play audio."""
    if 'current_mission' not in mission_data_storage:
        print("No mission created yet. Please create a mission first.")
        return

    mission_id = mission_data_storage['current_mission'].get("id")
    if not mission_id:
        print("Mission ID is missing. Cannot proceed.")
        return

    print(f"\nPolling status for mission: {mission_id}")
    while True:
        try:
            async with session.get(f"{BASE_URL}/mission_status/{mission_id}") as response:
                response.raise_for_status()
                status_data = await response.json()
                
                current_status = status_data.get("status")
                print(f"Current status: {current_status}")

                if current_status == "stage2":
                    print("Stage 2 reached! Connecting to WebSocket...")
                    break
                
                await asyncio.sleep(2) # Non-blocking sleep

        except aiohttp.ClientError as e:
            print(f"An error occurred while polling: {e}")
            return

    # Connect to WebSocket and stream audio
    uri = f"ws://localhost:8000/api/v1/ws/{mission_id}"
    try:
        async with websockets.connect(uri) as websocket:
            print("\nWebSocket connection established. Receiving audio stream...")
            print("Press Ctrl+C to disconnect.")
            
            # Setup audio stream
            stream = sd.OutputStream(samplerate=SAMPLE_RATE, channels=1, dtype='int16')
            stream.start()

            try:
                while True:
                    audio_chunk = await websocket.recv()
                    if isinstance(audio_chunk, bytes):
                        print(f"[TestClient] Received audio chunk: {len(audio_chunk)} bytes, head={audio_chunk[:8].hex() if len(audio_chunk) >= 8 else audio_chunk.hex()}.")
                        audio_data = np.frombuffer(audio_chunk, dtype=np.int16)
                        print(f"[TestClient] Writing audio chunk to stream: {audio_data.shape} samples.")
                        stream.write(audio_data)
                        print(f"[TestClient] Finished writing chunk.")
                    else:
                        print(f"[TestClient] Received non-bytes message: {audio_chunk}")
            except websockets.exceptions.ConnectionClosed:
                print("\nWebSocket connection closed by the server.")
            finally:
                stream.stop()
                stream.close()
                
    except Exception as e:
        print(f"WebSocket connection or audio playback failed: {e}")


async def main():
    """Main function to run the test script."""
    print("NOTE: This script requires 'sounddevice', 'numpy', and 'aiohttp'.")
    print("Install them with: pip install sounddevice numpy aiohttp")
    
    async with aiohttp.ClientSession() as session:
        while True:
            print("\n--- Test Menu ---")
            print("1. Create a new mission")
            print("2. Poll status and play radio broadcast")
            print("3. Exit")
            
            choice = input("Enter your choice: ")
            
            if choice == '1':
                await create_mission(session)
            elif choice == '2':
                await poll_and_connect(session)
            elif choice == '3':
                break
            else:
                print("Invalid choice. Please try again.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting script.")
        sys.exit(0)