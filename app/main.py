import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware # Added import
from app.api.v1.endpoints import propaganda, game
from app.db.mongodb_utils import connect_to_mongo, close_mongo_connection

# Configure logging
logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="Radio Mirchi Backend",
    description="Backend for the Radio Mirchi hackathon project.",
    version="0.1.0"
)

# CORS Middleware Configuration
origins = [
    "http://localhost",
    "http://localhost:3000", # Next.js frontend runs on port 3000
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], # Allows all methods
    allow_headers=["*"], # Allows all headers
)

@app.on_event("startup")
async def startup_event():
    await connect_to_mongo()

@app.on_event("shutdown")
async def shutdown_event():
    await close_mongo_connection()

app.include_router(propaganda.router, prefix="/api/v1", tags=["propaganda"])
app.include_router(game.router, prefix="/api/v1", tags=["game"])

@app.get("/")
def read_root():
    return {"message": "Welcome to the Radio Mirchi API"}