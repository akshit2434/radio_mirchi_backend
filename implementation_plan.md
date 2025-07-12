# Backend Implementation Plan

This document outlines the plan for implementing the Python backend for the Radio Mirchi hackathon project.

## Phase 1: Core Architecture & Mission Creation

### 1. Project Structure

We will organize the project with a clear and scalable structure.

```
.
├── app
│   ├── __init__.py
│   ├── main.py             # FastAPI app initialization
│   ├── api
│   │   ├── __init__.py
│   │   └── v1
│   │       ├── __init__.py
│   │       └── endpoints
│   │           ├── __init__.py
│   │           └── propaganda.py   # Endpoints for mission management
│   ├── core
│   │   ├── __init__.py
│   │   └── config.py         # Configuration settings
│   ├── db
│   │   ├── __init__.py
│   │   ├── mongodb_utils.py  # MongoDB connection utilities
│   │   └── propaganda_db.py    # Database operations for missions
│   ├── schemas
│   │   ├── __init__.py
│   │   └── propaganda.py   # Pydantic models for the application
│   └── services
│       ├── __init__.py
│       └── llm_service.py    # Service for Gemini integration
├── .gitignore
├── env.example
├── plan.md
├── implementation_plan.md
└── requirements.txt
```

### 2. Dependencies

We will add the required Python libraries to `requirements.txt`:

*   `fastapi`
*   `uvicorn`
*   `pydantic`
*   `pydantic-settings`
*   `google-generativeai`
*   `python-dotenv`
*   `deepgram-sdk`
*   `motor` # Async driver for MongoDB

### 3. Configuration

A `core/config.py` file will manage environment variables (like API keys and MongoDB URI) using `pydantic-settings`.

### 4. Pydantic Schemas

In `schemas/propaganda.py`, we define the Pydantic models that structure our application data, including the core `PropagandaMission` model.

```python
from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID, uuid4

class Speaker(BaseModel):
    name: str
    gender: str
    role: str
    background: str

class PropagandaGenerationResult(BaseModel):
    summary: str
    proof_sentences: List[str]
    speakers: List[Speaker] = Field(..., min_length=2)
    initial_listeners: int
    awakened_listeners: int = 0

class PropagandaMission(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    user_id: str
    topic: str
    status: str = "initializing"
    generation_result: PropagandaGenerationResult
    dialogue_generator_prompt: Optional[str] = None
    # ... other fields for dialogue history etc.
```

### 5. LLM Service

The `services/llm_service.py` contains the logic for interacting with the Gemini API. It's split into two main functions reflecting our two-stage generation process:

1.  `generate_initial_propaganda`: Synchronously called in Stage 1. Takes a topic and generates the base mission data (`PropagandaGenerationResult`).
2.  `generate_unified_dialogue_prompt`: Asynchronously called in Stage 2. Takes the generated mission data and creates a single, unified "Show & Character Briefing" prompt for the subsequent dialogue generation phase.

### 6. API Endpoints

The API is implemented in `api/v1/endpoints/propaganda.py` and provides two endpoints:

*   **`POST /api/v1/create_mission`**:
    *   **Purpose**: Kicks off the entire mission generation flow (Stage 1).
    *   **Request Body**: `{ "topic": "string", "user_id": "string" }`
    *   **Workflow**:
        1.  Receives a topic and user ID.
        2.  Synchronously calls `llm_service.generate_initial_propaganda`.
        3.  Saves the new mission to MongoDB with `status: "stage1"`.
        4.  Immediately returns the created `PropagandaMission` object.
        5.  Starts a background task to execute Stage 2 (generating the unified prompt).

*   **`GET /api/v1/mission_status/{mission_id}`**:
    *   **Purpose**: Allows the client to poll for the mission's status and get the latest data.
    *   **Workflow**:
        1.  Retrieves the mission from MongoDB by its UUID.
        2.  Returns the full `PropagandaMission` object, allowing the client to check the `status` field (e.g., for `"stage2"`) and access the `dialogue_generator_prompt` when ready.

### 7. FastAPI Application & Database Connection

The main FastAPI application in `app/main.py` initializes the API routers and manages the MongoDB connection lifecycle, ensuring the database is connected on startup and disconnected on shutdown.
## Phase 2: Interactive Dialogue Streaming via WebSockets

This phase covers the real-time, interactive part of the mission where the generated dialogue is streamed to the client as audio.

### 1. Project Structure Additions

The project structure is expanded to include WebSocket handling and game session management.

```
.
├── app
│   └── services
│       ├── deepgram_service.py # Service for TTS/STT
│       └── game_manager.py     # Manages active game sessions and connections
│   └── api
│       └── v1
│           └── endpoints
│               └── game.py         # WebSocket endpoint for interactive gameplay
```

### 2. Dependencies

The following libraries are essential for this phase:

*   `websockets` (included with `fastapi[all]`)
*   `sounddevice` and `numpy` (for the test client to play audio)

### 3. WebSocket Endpoint

A new endpoint is created in `api/v1/endpoints/game.py` to manage the live game session.

*   **`WS /api/v1/ws/{mission_id}`**:
    *   **Purpose**: Establishes a persistent connection for real-time, two-way communication.
    *   **Workflow**:
        1.  Accepts a WebSocket connection and associates it with a `mission_id`.
        2.  Creates a `GameSession` object to manage the state and logic for that specific mission.
        3.  Starts the game session's main loop as a background task.
        4.  Enters a loop to listen for incoming JSON messages from the client.
        5.  When it receives `{"action": "ready_for_next"}`, it signals the `GameSession` to proceed with the next dialogue line.
        6.  Handles `WebSocketDisconnect` exceptions to gracefully terminate the `GameSession` and clean up resources.

### 4. Game Session Management

The core of the interactive experience is handled by `services/game_manager.py`.

*   **`ConnectionManager` Class**: A simple manager that keeps track of active WebSocket connections, mapping a `mission_id` to its `WebSocket` object.

*   **`GameSession` Class**: This class encapsulates all the logic for a running mission.
    *   **State**: Holds the mission context, dialogue history, and a queue of upcoming dialogue lines.
    *   **Signaling**: Uses an `asyncio.Event` as a signal to control the flow. The session's main loop `waits` on this event before generating and streaming the next line.
    *   **Main Loop (`_dialogue_and_speaking_loop`)**:
        1.  Waits for the "ready" signal.
        2.  If the dialogue queue is empty, it calls the `llm_service` to generate the next batch of dialogues.
        3.  It takes the next line, calls the `deepgram_service` to get a streaming TTS audio generator.
        4.  It iterates through the generator, sending each audio chunk (`bytes`) directly to the client over the WebSocket.
        5.  After the last chunk, it sends a JSON message `{"status": "dialogue_end"}` to the client.
        6.  The loop then returns to step 1, waiting for the next signal.

### 5. Text-to-Speech Service

The `services/deepgram_service.py` provides the TTS functionality.

*   **`text_to_speech_stream` Method**:
    *   Takes text and speaker/voice parameters.
    *   Calls the Deepgram API and returns an `async_generator` that yields the audio data in chunks. This is critical for real-time streaming, as it allows the server to send audio to the client as soon as the first bytes are received from the TTS provider, minimizing latency.