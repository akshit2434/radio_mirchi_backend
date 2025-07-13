# Backend API Integration Guide for Next.js Frontend

This document outlines how to connect a frontend application to the real-time dialogue backend. The flow is based on the reference implementation in `tests/test_flow.py`.

## Overview

The interaction is a stateful, multi-step process:
1.  **HTTP Mission Creation**: The client initiates a "mission" (a dialogue session) via a standard HTTP POST request.
2.  **HTTP Polling**: The client polls an HTTP endpoint to check if the mission is ready.
3.  **WebSocket Communication**: Once ready, the client connects to a WebSocket server for real-time, bidirectional communication, sending user audio and receiving AI-generated speech.

---

## 1. API Configuration

-   **Base HTTP URL**: `http://localhost:8000/api/v1`
-   **Base WebSocket URL**: `ws://localhost:8000/api/v1`

---

## 2. API Flow

### Step 1: Create a Mission

To start a new dialogue session, send a POST request to the `create_mission` endpoint. This will create a unique session on the backend.

-   **Endpoint**: `POST /api/v1/create_mission`
-   **Method**: `POST`
-   **Headers**: `Content-Type: application/json`
-   **Request Body**:
    ```json
    {
      "topic": "The mission topic you want to discuss",
      "user_id": "A unique identifier for the user"
    }
    ```
-   **Success Response (200 OK)**:
    The server responds with the mission details, including the crucial `id` which you must store for all subsequent requests.
    ```json
    {
        "id": "m_a1b2c3d4e5f6",
        "user_id": "user_123",
        "topic": "The mission topic you want to discuss",
        "status": "stage1",
        "created_at": "2023-10-27T10:00:00.000Z",
        "summary": null,
        "propaganda_history": []
    }
    ```

### Step 2: Poll for Mission Status

After creating the mission, the backend needs a moment to initialize the AI models. The frontend must poll the `mission_status` endpoint until the status changes to `"stage2"`.

-   **Endpoint**: `GET /api/v1/mission_status/{mission_id}`
-   **Method**: `GET`
-   **Example URL**: `http://localhost:8000/api/v1/mission_status/m_a1b2c3d4e5f6`
-   **Polling Logic**:
    -   Make a request to this endpoint every 2-3 seconds.
    -   Check the `status` field in the JSON response.
    -   Continue polling as long as the status is `"stage1"`.
    -   When the status becomes `"stage2"`, the backend is ready. Stop polling and proceed to the next step.
-   **Response Body**:
    ```json
    {
      "status": "stage1" 
    }
    ```
    or
    ```json
    {
      "status": "stage2"
    }
    ```

### Step 3: Establish WebSocket Connection

Once the mission status is `"stage2"`, connect to the WebSocket endpoint to begin the real-time conversation.

-   **Endpoint**: `ws://localhost:8000/api/v1/ws/{mission_id}`
-   **Example URL**: `ws://localhost:8000/api/v1/ws/m_a1b2c3d4e5f6`

---

## 3. WebSocket Communication Protocol

The WebSocket connection is bidirectional. The client sends user audio and control messages, and the server sends AI speech and control messages.

### Audio Formats

-   **Client to Server (User Speech)**: The audio from the user's microphone **must** be in the following format for the server's Speech-to-Text to work correctly:
    -   **Sample Rate**: 16,000 Hz (16kHz)
    -   **Encoding**: 16-bit PCM
    -   **Channels**: 1 (Mono)
-   **Server to Client (AI Speech)**: The audio from the server's Text-to-Speech engine will be in the following format:
    -   **Sample Rate**: 24,000 Hz (24kHz)
    -   **Encoding**: 16-bit PCM
    -   **Channels**: 1 (Mono)

### Message Types

Communication involves two types of messages: **JSON objects** for control and **binary data** for audio.

#### **Client -> Server Messages**

| Type          | Format | Message                               | Description                                                                                                |
|---------------|--------|---------------------------------------|------------------------------------------------------------------------------------------------------------|
| Control (JSON)| `string` | `{"action": "start_speech"}`          | Sent **once** when the user presses the push-to-talk button. Informs the server to start listening.        |
| Audio         | `binary` | `(raw audio bytes)`                   | Streamed continuously while the user is speaking.                                                          |
| Control (JSON)| `string` | `{"action": "stop_speech"}`           | Sent **once** when the user releases the push-to-talk button. Informs the server to process the transcript.|
| Control (JSON)| `string` | `{"action": "ready_for_next"}`        | Sent after the AI finishes speaking to signal that the client is ready for the next round of user input.   |

#### **Server -> Client Messages**

| Type          | Format | Message                               | Description                                                                                                |
|---------------|--------|---------------------------------------|------------------------------------------------------------------------------------------------------------|
| Audio         | `binary` | `(raw audio bytes)`                   | Streamed from the server as the AI generates speech. The client should buffer and play this audio immediately. |
| Control (JSON)| `string` | `{"status": "dialogue_end"}`          | Sent after the AI audio stream is complete. This is the client's cue to prepare for the next user turn.    |

---

## 4. The Interaction Loop (Putting It All Together)

This is the core lifecycle of the conversation after the WebSocket is connected.

1.  **AI Speaks**: The server sends a stream of binary audio data. The client plays it as it arrives.
2.  **AI Finishes**: The server sends a JSON message: `{"status": "dialogue_end"}`.
3.  **Client Gets Ready**: The client ensures all buffered AI audio has finished playing.
4.  **Client Signals Readiness**: The client sends a JSON message: `{"action": "ready_for_next"}`. The system is now waiting for the user.
5.  **User Starts Speaking**: The user presses and holds the push-to-talk button.
    -   The client immediately sends the JSON message: `{"action": "start_speech"}`.
    -   The client begins capturing microphone audio (at 16kHz) and sending it as a stream of binary messages.
6.  **User Stops Speaking**: The user releases the push-to-talk button.
    -   The client immediately sends the JSON message: `{"action": "stop_speech"}`.
    -   The client stops capturing and sending audio.
7.  **Loop Repeats**: The server processes the user's speech, generates a response, and the loop begins again from step 1.

## 5. Frontend Implementation Notes (Next.js)

-   **WebSocket Client**: Use the browser's native `WebSocket` API to connect to the server.
-   **Audio Capture**:
    -   The Web Audio API (`AudioContext`, `MediaStreamAudioSourceNode`) is the standard way to capture microphone input.
    -   You will likely need an `AudioWorkletProcessor` or a library like `recorder-js` to process the raw audio, downsample it to **16kHz**, and encode it as **16-bit PCM** before sending it over the WebSocket. This is the most complex part of the frontend implementation.
-   **Audio Playback**:
    -   To play the incoming 24kHz audio stream from the server, you can also use the Web Audio API.
    -   Create an `AudioBuffer`, fill it with the incoming binary data, and play it using an `AudioBufferSourceNode`. This approach gives you low-latency playback, which is essential for a conversational feel.
-   **State Management**: Use a state management library (like Zustand, Redux, or React Context) to manage the application's state (e.g., `isAITalking`, `isUserTalking`, `isReadyForInput`).