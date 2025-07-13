import asyncio
import json
import sys
import numpy as np
import sounddevice as sd
import websockets
import aiohttp
import queue
import threading
from pynput import keyboard

# --- Configuration ---
BASE_URL = "http://localhost:8000/api/v1"
TTS_SAMPLE_RATE = 24000  # Deepgram's Aura TTS output sample rate
MIC_SAMPLE_RATE = 16000  # Deepgram's STT input sample rate
CHANNELS = 1
BLOCKSIZE = 1600  # 100ms of audio at 16kHz

# --- Global State ---
mission_data_storage = {}
is_space_pressed = False
audio_input_q = asyncio.Queue()

def pretty_print_json(data):
    """Prints JSON data in a readable format."""
    print(json.dumps(data, indent=4))

# --- Audio Playback Thread ---
def audio_player_thread(audio_q: queue.Queue):
    """
    A dedicated thread for playing audio from a queue. It buffers incoming byte chunks
    to ensure that only complete audio samples (multiples of 2 bytes for int16) are played.
    """
    stream = sd.OutputStream(samplerate=TTS_SAMPLE_RATE, channels=CHANNELS, dtype='int16')
    stream.start()
    audio_buffer = bytearray()
    
    while True:
        chunk = audio_q.get()
        if chunk is None:
            break
            
        audio_buffer.extend(chunk)
        
        # Process and play audio in chunks that are a multiple of the sample size (2 bytes for int16)
        playable_size = (len(audio_buffer) // 2) * 2
        
        if playable_size > 0:
            data_to_play = audio_buffer[:playable_size]
            try:
                audio_chunk_np = np.frombuffer(data_to_play, dtype=np.int16)
                stream.write(audio_chunk_np)
            except Exception as e:
                print(f"[PLAYER-ERROR] Could not play audio chunk: {e}")
            
            # Keep the remainder in the buffer
            audio_buffer = audio_buffer[playable_size:]

    # Play any remaining audio in the buffer after the loop finishes
    if len(audio_buffer) > 0:
        # Pad with a zero byte if the buffer has an odd number of bytes
        if len(audio_buffer) % 2 != 0:
            audio_buffer.append(0)
        try:
            final_chunk = np.frombuffer(audio_buffer, dtype=np.int16)
            stream.write(final_chunk)
        except Exception as e:
            print(f"[PLAYER-ERROR] Could not play final audio buffer: {e}")
            
    stream.stop()
    stream.close()
    print("\n[PLAYER] Audio player thread finished.")

# --- Microphone Input Callback ---
def audio_input_callback(indata, frames, time, status):
    """This is called from a separate thread for each audio block."""
    if status:
        print(status, file=sys.stderr)
    if is_space_pressed:
        # Use the asyncio queue which is thread-safe
        audio_input_q.put_nowait(bytes(indata))

# --- Keyboard Listener ---
def on_press(key):
    global is_space_pressed
    if key == keyboard.Key.space and not is_space_pressed:
        is_space_pressed = True
        print("\n[PTT] Start speaking...")

def on_release(key):
    global is_space_pressed
    if key == keyboard.Key.space and is_space_pressed:
        is_space_pressed = False
        print("[PTT] Stopped speaking.")

# --- Core Application Logic ---
async def create_mission(session: aiohttp.ClientSession):
    """Calls the create_mission endpoint."""
    topic = input("Enter the mission topic: ")
    user_id = input("Enter your user ID: ")
    print("\nCreating mission...")
    try:
        async with session.post(
            f"{BASE_URL}/create_mission", json={"topic": topic, "user_id": user_id}
        ) as response:
            response.raise_for_status()
            mission_data = await response.json()
            if mission_id := mission_data.get("id"):
                mission_data_storage['current_mission'] = mission_data
                print("Mission created successfully!")
                pretty_print_json(mission_data)
            else:
                print("Error: Mission ID not found.")
    except aiohttp.ClientError as e:
        print(f"An error occurred: {e}")

async def poll_mission_status(session: aiohttp.ClientSession, mission_id: str):
    """Polls until the mission is ready (stage2)."""
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
                    return True
                await asyncio.sleep(2)
        except aiohttp.ClientError as e:
            print(f"An error occurred while polling: {e}")
            return False

async def handle_websocket_communication(uri: str):
    """Manages the entire WebSocket lifecycle including audio I/O."""
    audio_output_q = queue.Queue()
    player = threading.Thread(target=audio_player_thread, args=(audio_output_q,))
    player.start()

    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.start()

    print("\n[INFO] Push-to-talk is active. Press and hold SPACE to speak.")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("\n[SUCCESS] WebSocket connection established.")
            
            # Start the microphone stream
            with sd.InputStream(samplerate=MIC_SAMPLE_RATE, channels=CHANNELS, dtype='int16', blocksize=BLOCKSIZE, callback=audio_input_callback):
                
                # Task to send microphone audio to the server
                async def microphone_sender():
                    was_speaking = False
                    while True:
                        if is_space_pressed:
                            if not was_speaking:
                                await websocket.send(json.dumps({"action": "start_speech"}))
                                was_speaking = True
                            try:
                                audio_chunk = await audio_input_q.get()
                                await websocket.send(audio_chunk)
                                audio_input_q.task_done()
                            except asyncio.QueueEmpty:
                                await asyncio.sleep(0.01)
                        else:
                            if was_speaking:
                                await websocket.send(json.dumps({"action": "stop_speech"}))
                                was_speaking = False
                            await asyncio.sleep(0.05) # Small sleep to prevent busy-waiting

                # Task to receive server messages
                async def server_receiver():
                    while True:
                        try:
                            message = await websocket.recv()
                            if isinstance(message, bytes):
                                audio_output_q.put(message)
                            elif isinstance(message, str):
                                data = json.loads(message)
                                if data.get("status") == "dialogue_end":
                                    print("[SIGNAL] Received end-of-dialogue signal.")
                                    while not audio_output_q.empty():
                                        await asyncio.sleep(0.1)
                                    print("[SIGNAL] Audio queue empty. Sending 'ready_for_next'.")
                                    await websocket.send(json.dumps({"action": "ready_for_next"}))
                        except websockets.exceptions.ConnectionClosed:
                            print("\n[INFO] WebSocket connection closed by the server.")
                            break
                
                sender_task = asyncio.create_task(microphone_sender())
                receiver_task = asyncio.create_task(server_receiver())
                
                await asyncio.gather(sender_task, receiver_task)

    except Exception as e:
        print(f"\n[ERROR] An unexpected error occurred: {e}")
    finally:
        audio_output_q.put(None)
        player.join()
        listener.stop()
        print("[INFO] Client shutdown complete.")

async def main():
    """Main function to run the test script."""
    print("NOTE: This script requires 'sounddevice', 'numpy', 'aiohttp', and 'pynput'.")
    print("Install them with: pip install sounddevice numpy aiohttp pynput")
    
    async with aiohttp.ClientSession() as session:
        while True:
            print("\n--- Test Menu ---")
            print("1. Create a new mission")
            print("2. Connect to the last created mission")
            print("3. Connect to an existing mission by ID")
            print("4. Exit")
            
            choice = input("Enter your choice: ")
            
            mission_id = None
            if choice == '1':
                await create_mission(session)
                if 'current_mission' in mission_data_storage:
                    mission_id = mission_data_storage['current_mission'].get("id")
            elif choice == '2':
                if 'current_mission' in mission_data_storage:
                    mission_id = mission_data_storage['current_mission'].get("id")
                else:
                    print("No mission created yet.")
            elif choice == '3':
                mission_id = input("Enter the existing mission ID: ")
            elif choice == '4':
                break
            else:
                print("Invalid choice.")
                continue

            if mission_id:
                if await poll_mission_status(session, mission_id):
                    uri = f"ws://localhost:8000/api/v1/ws/{mission_id}"
                    await handle_websocket_communication(uri)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting script.")
        sys.exit(0)