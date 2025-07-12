import asyncio
import json
import sys
import numpy as np
import sounddevice as sd
import websockets
import aiohttp
import queue
import threading

BASE_URL = "http://localhost:8000/api/v1"
mission_data_storage = {}
SAMPLE_RATE = 24000  # The sample rate for Deepgram's Aura TTS models

def pretty_print_json(data):
    """Prints JSON data in a readable format."""
    print(json.dumps(data, indent=4))

def audio_player_thread(audio_q: queue.Queue):
    """
    A dedicated thread for playing audio from a queue to avoid blocking the main async loop.
    """
    stream = sd.OutputStream(samplerate=SAMPLE_RATE, channels=1, dtype='int16')
    stream.start()
    
    audio_buffer = bytearray()
    
    while True:
        try:
            # Block until a chunk is available
            chunk = audio_q.get()
            
            # A None chunk is the signal to stop
            if chunk is None:
                break
                
            audio_buffer.extend(chunk)
            
            playable_size = (len(audio_buffer) // 2) * 2
            
            if playable_size > 0:
                data_to_play = audio_buffer[:playable_size]
                
                try:
                    audio_chunk_np = np.frombuffer(data_to_play, dtype=np.int16)
                    stream.write(audio_chunk_np)
                except Exception as e:
                    print(f"[PLAYER-ERROR] Could not play audio chunk: {e}")
                    
                audio_buffer = audio_buffer[playable_size:]

        except Exception as e:
            print(f"[PLAYER-ERROR] An unexpected error occurred in the player thread: {e}")

    # Play any remaining audio
    if len(audio_buffer) > 0:
        if len(audio_buffer) % 2 != 0:
            audio_buffer.append(0) # Pad if necessary
        try:
            final_chunk = np.frombuffer(audio_buffer, dtype=np.int16)
            stream.write(final_chunk)
        except Exception as e:
            print(f"[PLAYER-ERROR] Could not play final audio buffer: {e}")
            
    stream.stop()
    stream.close()
    print("\n[PLAYER] Audio player thread finished.")


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
    """Polls for mission status, connects to WebSocket, and streams audio via a dedicated thread."""
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
                
                await asyncio.sleep(2)

        except aiohttp.ClientError as e:
            print(f"An error occurred while polling: {e}")
            return

    uri = f"ws://localhost:8000/api/v1/ws/{mission_id}"
    print("\n[LIVE MODE] This script will now play the audio stream from your speakers.")
    
    # Setup thread-safe queue and player thread
    audio_q = queue.Queue()
    player = threading.Thread(target=audio_player_thread, args=(audio_q,))
    player.start()
    
    total_bytes = 0

    try:
        async with websockets.connect(uri) as websocket:
            print("\n[SUCCESS] WebSocket connection established.")
            print("           Receiving audio stream...")
            
            while True:
                try:
                    message = await websocket.recv()
                    if isinstance(message, bytes):
                        chunk_size = len(message)
                        total_bytes += chunk_size
                        print(f"[DATA]    Received audio chunk of size: {chunk_size} bytes.")
                        audio_q.put(message)
                    else:
                        print(f"[WARN]    Received non-audio message: {message}")
                
                except websockets.exceptions.ConnectionClosed:
                    print("\n[INFO]    WebSocket connection closed by the server.")
                    break

    except Exception as e:
        print(f"\n[ERROR]   An unexpected error occurred in the main loop: {e}")
    
    finally:
        # Signal the player thread to exit and wait for it
        audio_q.put(None)
        player.join()
        
        print(f"\n[SUMMARY] Streaming finished. Total audio bytes received: {total_bytes}")
        if total_bytes == 0:
            print("[WARN]    No audio data was received.")


async def main():
    """Main function to run the test script."""
    print("NOTE: This script requires 'sounddevice', 'numpy', and 'aiohttp'.")
    print("Install them with: pip install sounddevice numpy aiohttp")
    
    async with aiohttp.ClientSession() as session:
        while True:
            print("\n--- Test Menu ---")
            print("1. Create a new mission")
            print("2. Poll status and stream audio for last created mission")
            print("3. Connect to an existing mission by ID")
            print("4. Exit")
            
            choice = input("Enter your choice: ")
            
            if choice == '1':
                await create_mission(session)
            elif choice == '2':
                await poll_and_connect(session)
            elif choice == '3':
                mission_id = input("Enter the existing mission ID: ")
                if mission_id:
                    # Store the provided ID so poll_and_connect can use it
                    mission_data_storage['current_mission'] = {"id": mission_id}
                    await poll_and_connect(session)
                else:
                    print("Invalid Mission ID provided.")
            elif choice == '4':
                break
            else:
                print("Invalid choice. Please try again.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting script.")
        sys.exit(0)