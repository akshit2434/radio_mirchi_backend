<!-- user logs in.
gets brief about mission 
    -> api call to generate story and task and keep stuff ready (asynchronously in mongodb with status=processing till finished, then status = completed). 
        -> return the brief about task

executes command to join into fm freq (let's say 93.5) 
    -> api call recieved. poll mongodb every sec till status changes from processing to finished.
        -> connect websocket
        
websocket connected
    -> send _name_ of each caller.
    -> continuously audio from user's mic is streamed to python backend in chunks
    keep doing this till timelimit:
        parallel task 1:
            -> generate 10 dialogues at once (or less if waiting for user's response) from gemini (use good system prompt, pass story and past dialogues as context)
            -> decide voice actors for each speaker. give _name_ to each.
            -> send json list with name and audio of each dialogue. gaps will be a segment too.
            -> stream the tts audio in segments to user if possible
        parallel task 2:
            -> use vad to check if user is speaking or interrupting.
            -> if they are:
                -> pause the audio stream being sent to user. also mark the context till where the dialogue was done and add a tag like "(user interrupted)".
                -> use user's audio chunks to do stt (speech to text). then when user is done, append the stt text to context and continue parallel task 1 with this context
            -> else:
                -> continue -->

with push to talk: (this is what we are doing)
    user logs in (handled by nextjs).
    gets brief about mission by:
        -> Making a POST request to `/api/v1/create_mission`.
        -> The API synchronously generates the initial mission details (story, characters, etc.) and saves it to the database with `status: "stage1"`.
        -> The API immediately returns this initial mission data.
        -> In the background, the server starts generating a unified dialogue prompt for the next phase, and updates the mission status to `status: "stage2"` when complete.

    executes command to join into fm freq (let's say 93.5)
        -> The client polls the `GET /api/v1/mission_status/{mission_id}` endpoint until the `status` field becomes `"stage2"`.
        -> Once the status is `"stage2"`, the client has the dialogue prompt and can connect to the WebSocket for the interactive phase.

    websocket connected
        -> The server initiates a `GameSession` to manage the interactive dialogue.
        -> The `GameSession` enters a continuous loop with the following logic:
        
        **Server-Side Logic (Dialogue Generation & Streaming):**
        1.  **Wait for Signal**: The server waits for a "ready" signal from the client before proceeding. For the very first line, it starts automatically.
        2.  **Generate Dialogue**: If its internal dialogue queue is empty, it generates a new batch of dialogues using the LLM, based on the mission context and past dialogue history.
        3.  **Stream Audio**: It takes the next dialogue line from its queue and generates TTS audio for it using Deepgram.
        4.  **Send Audio**: It streams the audio `bytes` to the client in real-time chunks.
        5.  **Signal End of Dialogue**: After the final audio chunk for a line is sent, the server sends a JSON message: `{"status": "dialogue_end"}`.
        6.  The server now waits again at step 1 for the client's signal.

        **Client-Side Logic (Audio Playback & Signaling):**
        1.  **Receive Audio**: The client receives audio `bytes` and puts them into a local queue for a dedicated audio player thread. This ensures the main connection doesn't block while sound is playing.
        2.  **Play Audio**: The audio player thread consumes the queue and plays the sound through the user's speakers in real-time.
        3.  **Receive End Signal**: When the client receives the `{"status": "dialogue_end"}` message, it knows the current line is complete.
        4.  **Confirm Playback Finished**: The client waits for its local audio queue to become empty, confirming that all received audio has been played.
        5.  **Signal Ready**: Once playback is finished, it sends a JSON message `{"action": "ready_for_next"}` back to the server.
        
        -> This two-way signaling loop continues, ensuring a strict, sequential, and robust dialogue playback experience.

## Technology Stack & Core Mechanics

*   **Web Framework**: FastAPI will be used for the backend API. It's modern, fast, and has great support for Pydantic models which we'll use for structured data.
*   **Language Model (LLM)**: We are using Google's `gemini-2.5-flash` model via the `google-genai` Python library for all content generation tasks, including the initial mission. For dialogue prompts we'll use `gemini-2.5-flash-lite-preview-06-17` for fastest response.
*   **Text-to-Speech (TTS) & Speech-to-Text (STT)**: We will use the `deepgram-sdk` for Python for all speech synthesis and recognition tasks.
*   **Database**: MongoDB will be used for storing mission data, status, and context.

### Game Mechanics

*   **Listeners**: When a mission starts, Gemini will generate the initial number of listeners for the radio show.
*   **Awakened Listeners**: The game will track the number of "awakened" listeners, starting at 0.
*   **Awakening Metric**: The user's performance in conversations will determine how many listeners are "awakened". This metric will be generated by Gemini alongside the dialogue responses. We will use Pydantic models to ensure Gemini provides this data in a structured format (e.g., `{"dialogues": ["...","..."], "awakened_listeners_change_percent": -5}`).