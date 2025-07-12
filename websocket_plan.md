# WebSocket Implementation Plan

This document outlines the detailed plan for the real-time, interactive WebSocket-based gameplay.

## 1. Core Components & Architecture

We will introduce several new components to manage the complex, stateful nature of the WebSocket interaction.

*   **`ConnectionManager`**: A singleton class to manage active WebSocket connections, mapping `mission_id` to a specific `WebSocket` object.
*   **`GameSession`**: A class to encapsulate the state and logic for a single mission's game session. Each connected client will have a corresponding `GameSession` instance.
*   **`DeepgramService`**: A new service in `app/services` to handle both live streaming STT and on-demand TTS.
*   **In-Memory Dialogue Queue**: Each `GameSession` will maintain a queue of upcoming dialogue lines to ensure smooth playback without waiting for the LLM.

## 2. WebSocket Lifecycle & Game Flow

The entire process will be managed within the `/ws/{mission_id}` endpoint in `app/api/v1/endpoints/game.py`.

### Step 1: Connection & Initialization

1.  When a client connects, the `ConnectionManager` registers the WebSocket.
2.  A `GameSession` instance is created for the `mission_id`.
3.  The server immediately triggers the **first dialogue generation** by calling a new function in `llm_service.py`. This function will use the `dialogue_generator_prompt` (created in Stage 2) to generate the initial set of dialogues (e.g., 5-10 lines).
4.  The generated dialogues are loaded into the `GameSession`'s dialogue queue.

### Step 2: Host Dialogue & Audio Streaming

1.  The `GameSession` begins processing its dialogue queue.
2.  For each dialogue line:
    a. The text is sent to the `DeepgramService` for on-the-fly TTS.
    b. The returned audio is streamed back to the client over the WebSocket in chunks.
    c. A JSON message indicating the speaker (`{"speaker": "Host A", "type": "dialogue_chunk"}`) is sent alongside the audio.
3.  **Proactive Dialogue Fetching**: When the dialogue queue has only 2-3 lines left, the `GameSession` will automatically trigger another call to the LLM in the background to fetch the next batch of dialogues, ensuring the queue never runs dry.

### Step 3: User Interaction (Push-to-Talk)

This flow is initiated when the client sends a specific message (e.g., `{"event": "start_speaking"}`).

1.  **Receiving User Audio**:
    a. The client starts streaming audio chunks to the backend.
    b. The `GameSession` immediately forwards these raw audio chunks to the `DeepgramService` for live STT.
    c. The `DeepgramService` maintains a persistent connection to Deepgram for the duration of the user's speech.

2.  **Handling End of Speech**:
    a. The client signals the end of speech by sending a message (e.g., `{"event": "stop_speaking"}`).
    b. The `GameSession` closes the streaming connection to Deepgram.
    c. The final, complete transcript is received from the `DeepgramService`.

3.  **Context Update & Re-generation**:
    a. The transcribed text is appended to the mission's dialogue history/context in the database.
    b. The `GameSession` immediately triggers a new dialogue generation cycle from the LLM, providing the updated context. This ensures the hosts' responses are relevant to what the user just said.
    c. The newly generated dialogues are added to the queue, and the host speaking cycle (Step 2) resumes.

## 3. State Management

The `GameSession` will manage the state of the interaction, which can include:

*   `HOST_SPEAKING`: The server is actively streaming host dialogue.
*   `WAITING_FOR_USER`: The hosts have paused, and the server is waiting for the user to initiate speech.
*   `USER_SPEAKING`: The server is actively receiving and transcribing user audio.

This state machine will ensure that events are handled correctly (e.g., preventing hosts from speaking while the user is talking).

## 4. Data Flow Diagram

```
[Client] -- (Connects to /ws/{mission_id}) --> [FastAPI Backend]
    |                                                 |
    | <--- (Streamed Host TTS Audio) ----------------- | (1. Generate initial dialogues)
    |                                                 | (2. Stream TTS to client)
    |                                                 | (3. Proactively fetch next dialogues)
    |                                                 |
    | -- (User Audio Stream via PTT) --> [Deepgram STT] -- (Transcript) --> [Update Context & Re-gen Dialogue]
    |                                                 |
    | <--- (New, Context-Aware Host Audio) ----------- |