# 🧠 Radio Mirchi Backend

This is the backend for [Radio Mirchi](https://github.com/akshit2434/radio_mirchi), a retro-inspired browser game where you play as an underground agent infiltrating AI-generated radio broadcasts to fight propaganda.

## 🚦 Overview

This backend powers the game logic, AI-driven propaganda generation, and real-time communication with the frontend. It is built for the OSDCHack 25' Hackathon.

- **Language:** Python 3.10+
- **Framework:** FastAPI
- **Database:** MongoDB
- **Audio Processing:** Deepgram API (for speech-to-text)
- **AI/LLM:** Integrates with LLM services for dynamic content

## 📦 Features

- Game session management and state tracking
- AI-generated propaganda and host personalities
- Real-time game events via WebSockets
- Listener influence and win/loss logic
- Secure endpoints for game actions
- MongoDB for persistent storage

## 🚀 Getting Started

### Prerequisites

- Python 3.10+
- [MongoDB](https://www.mongodb.com/) running locally or remotely
- [Deepgram API Key](https://deepgram.com/) (for speech-to-text)
- (Optional) Docker

### Setup

1. **Clone the repo:**
   ```bash
   git clone https://github.com/akshit2434/radio_mirchi_backend.git
   cd radio_mirchi_backend
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment:**
   - Copy `env.example` to `.env` and fill in your MongoDB URI and Deepgram API key.

4. **Run the backend:**
   ```bash
   uvicorn app.main:app --reload
   ```

   Or with Docker:
   ```bash
   docker-compose up --build
   ```

### API Documentation

Once running, visit [http://localhost:8000/docs](http://localhost:8000/docs) for interactive API docs (Swagger UI).

## 🛠️ Project Structure

```
app/
  ├── api/                # API endpoints (FastAPI routers)
  ├── core/               # Core config and settings
  ├── db/                 # Database utilities (MongoDB)
  ├── schemas/            # Pydantic models (request/response)
  ├── services/           # Game, LLM, and Deepgram logic
  └── main.py             # FastAPI app entrypoint
tests/                    # Unit tests
```

## 🔗 Related

- **Frontend:** [Radio Mirchi Frontend](https://github.com/akshit2434/radio_mirchi)
- **Sounds:** [Pixabay retro sounds](https://pixabay.com/sound-effects/search/retro/)

## 📝 License

MIT License — use, modify, and share freely.

---

*Made with ☕, Python, and a love for all things retro*
