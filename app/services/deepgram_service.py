import asyncio
import random
import threading
import traceback
from deepgram import (
    DeepgramClient,
    LiveOptions,
    LiveTranscriptionEvents,
    SpeakWebSocketEvents,
)
from app.core.config import settings

# --- Voice Models ---
MALE_VOICES = [
    "aura-2-odysseus-en", "aura-2-apollo-en", "aura-2-arcas-en", "aura-2-aries-en",
    "aura-2-atlas-en", "aura-2-draco-en", "aura-2-hermes-en", "aura-2-hyperion-en",
    "aura-2-jupiter-en", "aura-2-mars-en", "aura-2-neptune-en", "aura-2-orion-en",
    "aura-2-orpheus-en", "aura-2-pluto-en", "aura-2-saturn-en", "aura-2-zeus-en"
]

FEMALE_VOICES = [
    "aura-2-thalia-en", "aura-2-amalthea-en", "aura-2-andromeda-en", "aura-2-asteria-en",
    "aura-2-athena-en", "aura-2-aurora-en", "aura-2-callista-en", "aura-2-cora-en",
    "aura-2-cordelia-en", "aura-2-delia-en", "aura-2-electra-en", "aura-2-harmonia-en",
    "aura-2-helena-en", "aura-2-hera-en", "aura-2-iris-en", "aura-2-janus-en",
    "aura-2-juno-en", "aura-2-luna-en", "aura-2-minerva-en", "aura-2-ophelia-en",
    "aura-2-pandora-en", "aura-2-phoebe-en", "aura-2-selene-en", "aura-2-theia-en",
    "aura-2-vesta-en"
]

class DeepgramService:
    """
    A service to interact with Deepgram's APIs for Text-to-Speech and Speech-to-Text.
    """
    def __init__(self):
        self.client = DeepgramClient(settings.DEEPGRAM_API_KEY)

    async def text_to_speech_stream(self, text: str, gender: str):
        """
        Connects to Deepgram's TTS WebSocket, sends text, and yields audio chunks.
        """
        if gender.lower() == 'male':
            model = random.choice(MALE_VOICES)
        else:
            model = random.choice(FEMALE_VOICES)
        
        print(f"Using voice model: {model}")

        options = {
            "model": model,
            "encoding": "linear16",
            "sample_rate": 24000,
        }
        
        dg_connection = self.client.speak.websocket.v("1")
        audio_queue = asyncio.Queue()
        
        def on_audio_data(connection, data, **kwargs):
            print(f"[DeepgramService] Received audio chunk from Deepgram: {len(data)} bytes, head={data[:8].hex() if isinstance(data, bytes) else 'N/A'}")
            audio_queue.put_nowait(data)

        def on_close(connection, code, **kwargs):
            reason = kwargs.get("reason", "Reason not provided.")
            print(f"Deepgram connection closed gracefully: code={code}, reason='{reason}'")
            audio_queue.put_nowait(None)

        def on_error(connection, error, **kwargs):
            print(f"Deepgram error: {error}")
            print(traceback.format_exc())
            audio_queue.put_nowait(None)

        dg_connection.on(SpeakWebSocketEvents.AudioData, on_audio_data)
        dg_connection.on(SpeakWebSocketEvents.Close, on_close)
        dg_connection.on(SpeakWebSocketEvents.Error, on_error)

        def run_deepgram_tts():
            try:
                if dg_connection.start(options) is False:
                    print("Failed to start Deepgram TTS connection")
                    audio_queue.put_nowait(None)
                    return
                
                dg_connection.send_text(text)
                # dg_connection.finish() # This is handled by the Close event now
            except Exception as e:
                print(f"Unhandled error in Deepgram TTS thread: {e}")
                print(traceback.format_exc())
                audio_queue.put_nowait(None)

        thread = threading.Thread(target=run_deepgram_tts)
        thread.start()

        while True:
            chunk = await audio_queue.get()
            if chunk is None:
                print("[DeepgramService] End of audio stream from Deepgram.")
                break
            print(f"[DeepgramService] Yielding audio chunk: {len(chunk)} bytes, head={chunk[:8].hex() if isinstance(chunk, bytes) else 'N/A'}")
            yield chunk
        
        thread.join()

    def get_live_transcriber(self, on_transcript_callback):
        """
        Creates and returns a configured synchronous Deepgram live transcription connection.
        """
        dg_connection = self.client.listen.websocket.v("1")
        options = LiveOptions(
            smart_format=True,
            model="nova-2",
            language="en-US",
            encoding="linear16",
            sample_rate=16000,
        )
        return dg_connection, options

# Singleton instance for easy access
deepgram_service = DeepgramService()