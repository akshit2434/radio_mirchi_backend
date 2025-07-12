import asyncio
import json
import sys
import numpy as np
import sounddevice as sd
import websockets
import aiohttp
import wave

BASE_URL = "http://localhost:8000/api/v1"
mission_data_storage = {}
SAMPLE_RATE = 24000  # The sample rate for Deepgram's Aura TTS models
OUTPUT_FILENAME = "output.wav"

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
    received_audio_bytes = bytearray()
    
    print("\n[DIAGNOSTIC MODE] This script will now save the audio stream to a file instead of playing it.")
    print(f"                  The output file will be named '{OUTPUT_FILENAME}'.")

    try:
        async with websockets.connect(uri) as websocket:
            print("\n[SUCCESS] WebSocket connection established.")
            print("           Receiving audio stream...")
            
            while True:
                try:
                    message = await websocket.recv()
                    if isinstance(message, bytes):
                        chunk_size = len(message)
                        print(f"[DATA]    Received audio chunk of size: {chunk_size} bytes.")
                        received_audio_bytes.extend(message)
                    else:
                        print(f"[WARN]    Received non-audio message: {message}")
                
                except websockets.exceptions.ConnectionClosed:
                    print("\n[INFO]    WebSocket connection closed by the server.")
                    break

    except Exception as e:
        print(f"\n[ERROR]   An unexpected error occurred: {e}")
    
    finally:
        total_bytes = len(received_audio_bytes)
        print(f"\n[SUMMARY] Streaming finished. Total audio bytes received: {total_bytes}")
        
        if total_bytes > 0:
            print(f"[SAVE]    Saving received audio to '{OUTPUT_FILENAME}'...")
            try:
                with wave.open(OUTPUT_FILENAME, 'wb') as wf:
                    wf.setnchannels(1)  # Mono
                    wf.setsampwidth(2)  # 16-bit = 2 bytes
                    wf.setframerate(SAMPLE_RATE)
                    wf.writeframes(received_audio_bytes)
                print(f"[SUCCESS] Audio saved successfully to '{OUTPUT_FILENAME}'.")
                print("           Please play this file to check if the audio is correct.")
            except Exception as e:
                print(f"[ERROR]   Failed to save .wav file: {e}")
        else:
            print("[WARN]    No audio data was received, so no file was saved.")


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