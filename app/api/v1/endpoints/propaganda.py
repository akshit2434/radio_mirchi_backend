from fastapi import APIRouter, HTTPException
from app.schemas.propaganda import Propaganda, PropagandaCreate
from app.services import llm_service
from app.services.llm_service import LLMServiceError

router = APIRouter()

@router.post("/create_propaganda", response_model=Propaganda)
def create_propaganda_endpoint(propaganda_in: PropagandaCreate):
    """
    Create a new propaganda mission.
    """
    try:
        propaganda = llm_service.generate_propaganda(topic=propaganda_in.topic)
        return propaganda
    except LLMServiceError as e:
        raise HTTPException(status_code=500, detail=str(e))