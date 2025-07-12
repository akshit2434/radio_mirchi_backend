from fastapi import FastAPI
from app.api.v1.endpoints import propaganda

app = FastAPI(
    title="Radio Mirchi Backend",
    description="Backend for the Radio Mirchi hackathon project.",
    version="0.1.0"
)

app.include_router(propaganda.router, prefix="/api/v1", tags=["propaganda"])

@app.get("/")
def read_root():
    return {"message": "Welcome to the Radio Mirchi API"}