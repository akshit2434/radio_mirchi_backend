import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    MONGODB_URI: str
    MONGODB_DB: str
    DEEPGRAM_API_KEY: str
    GOOGLE_API_KEY: str
    SECRET_KEY: str
    API_SECRET: str
    HOST: str
    PORT: int

    def __init__(self):
        # MongoDB Configuration
        self.MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
        self.MONGODB_DB = os.getenv("MONGODB_DB", "radio_mirchi")

        # Deepgram Configuration
        deepgram_api_key = os.getenv("DEEPGRAM_API_KEY")
        if deepgram_api_key is None:
            raise ValueError("DEEPGRAM_API_KEY environment variable not set.")
        self.DEEPGRAM_API_KEY = deepgram_api_key

        # Google Gemini Configuration
        google_api_key = os.getenv("GOOGLE_API_KEY")
        if google_api_key is None:
            raise ValueError("GOOGLE_API_KEY environment variable not set.")
        self.GOOGLE_API_KEY = google_api_key

        # Application Configuration
        self.SECRET_KEY = os.getenv("SECRET_KEY", "your_secret_key_here")
        self.API_SECRET = os.getenv("API_SECRET", "your_api_secret_here")

        # Server Configuration
        self.HOST = os.getenv("HOST", "0.0.0.0")
        self.PORT = int(os.getenv("PORT", 8000))

settings = Settings()