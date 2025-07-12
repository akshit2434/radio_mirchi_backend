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