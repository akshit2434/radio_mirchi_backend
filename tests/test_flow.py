import requests
import time
import asyncio
import websockets
import json

BASE_URL = "http://localhost:8000/api/v1"
mission_data_storage = {}

def pretty_print_json(data):
    """Prints JSON data in a readable format."""
    print(json.dumps(data, indent=4))

async def create_mission():
    """Calls the create_mission endpoint and stores the mission data."""
    topic = input("Enter the mission topic: ")
    user_id = input("Enter your user ID: ")
    
    print("\nCreating mission...")
    try:
        response = requests.post(f"{BASE_URL}/create_mission", json={"topic": topic, "user_id": user_id})
        response.raise_for_status()
        
        mission_data = response.json()
        mission_id = mission_data.get("id")
        
        if mission_id:
            mission_data_storage['current_mission'] = mission_data
            print("Mission created successfully!")
            pretty_print_json(mission_data)
        else:
            print("Error: Mission ID not found in the response.")
            pretty_print_json(mission_data)
            
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")

async def poll_and_connect():
    """Polls for mission status and connects to the WebSocket."""
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
            response = requests.get(f"{BASE_URL}/mission_status/{mission_id}")
            response.raise_for_status()
            status_data = response.json()
            
            current_status = status_data.get("status")
            print(f"Current status: {current_status}")

            if current_status == "stage2":
                print("Stage 2 reached! Connecting to WebSocket...")
                break
            
            time.sleep(2) # Poll every 2 seconds

        except requests.exceptions.RequestException as e:
            print(f"An error occurred while polling: {e}")
            return

    # Connect to WebSocket
    uri = f"ws://localhost:8000/api/v1/ws/{mission_id}"
    try:
        async with websockets.connect(uri) as websocket:
            print("WebSocket connection established.")
            
            # Send a demo message
            demo_message = "Hello from the test client!"
            await websocket.send(demo_message)
            print(f"> Sent: {demo_message}")
            
            # Wait for a response
            response = await websocket.recv()
            print(f"< Received: {response}")
            
    except Exception as e:
        print(f"WebSocket connection failed: {e}")


async def main():
    """Main function to run the test script."""
    while True:
        print("\n--- Test Menu ---")
        print("1. Create a new mission")
        print("2. Poll status and connect to WebSocket")
        print("3. Exit")
        
        choice = input("Enter your choice: ")
        
        if choice == '1':
            await create_mission()
        elif choice == '2':
            await poll_and_connect()
        elif choice == '3':
            break
        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    asyncio.run(main())