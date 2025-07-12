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
        -> api call to generate story and task and keep stuff ready (asynchronously in mongodb with status=processing till finished, then status = completed).
            -> return the brief about task

    executes command to join into fm freq (let's say 93.5)
        -> api call received. poll mongodb every sec till status changes from processing to finished.
            -> connect websocket

    websocket connected
        -> send _name_ of each caller.
        -> main loop until timelimit:
            -> if current dialogue segment is a pause for user to speak:
                -> wait up to 10 seconds for user to press and hold the "Talk" button.
                -> if user presses button:
                    -> while button is pressed, record and stream user's mic audio to python backend in chunks.
                    -> on button release, stop recording and send final audio chunk.
                    -> backend performs STT on received audio.
                        -> if STT detects that audio is blank, add "user spoke nothing" to context (same as else above).
                        -> else, append transcribed text to context.
                -> else (user does not speak within 10 seconds):
                    -> add "user spoke nothing" to context.
            -> generate next set of dialogues from gemini (use good system prompt, pass story and past dialogues as context).
            -> decide voice actors for each speaker. give _name_ to each.
            -> send json list with name and audio of each dialogue. gaps will be a segment too.
            -> stream the tts audio in segments to user if possible.
        -> repeat for each dialogue segment until timelimit.