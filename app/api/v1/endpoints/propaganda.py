import asyncio
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from uuid import UUID
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.schemas.propaganda import (
    PropagandaMission,
    PropagandaCreateRequest,
)
from app.services import llm_service
from app.db.mongodb_utils import get_database
from app.db import propaganda_db

router = APIRouter()

async def generate_and_store_system_prompts(mission: PropagandaMission, db: AsyncIOMotorDatabase):
    """
    Background task (Stage 2): Generate system prompts for each speaker and update the mission.
    """
    try:
        updated_speakers = []
        for speaker in mission.generation_result.speakers:
            system_prompt = await asyncio.to_thread(
                llm_service.generate_speaker_system_prompt,
                topic=mission.topic,
                speaker=speaker
            )
            speaker.system_prompt = system_prompt
            updated_speakers.append(speaker)

        # Prepare data for update
        update_data = {
            "generation_result.speakers": [s.model_dump() for s in updated_speakers],
            "status": "stage2"
        }

        # Update the mission in the database
        await propaganda_db.update_propaganda_mission(mission.id, update_data, db)

    except llm_service.LLMServiceError as e:
        await propaganda_db.update_propaganda_mission(mission.id, {"status": "stage2_failed"}, db)
    except Exception as e:
        await propaganda_db.update_propaganda_mission(mission.id, {"status": "stage2_failed"}, db)


@router.post("/create_mission", response_model=PropagandaMission, status_code=201)
async def create_mission(
    request: PropagandaCreateRequest,
    background_tasks: BackgroundTasks,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Creates a new propaganda mission (Stage 1).

    This endpoint synchronously generates the initial mission details,
    returns them, and then starts a background task to generate detailed
    system prompts for each speaker (Stage 2).
    """
    try:
        # 1. Generate initial propaganda content (synchronous)
        generation_result = await asyncio.to_thread(
            llm_service.generate_initial_propaganda, topic=request.topic
        )

        # 2. Create the full mission object
        mission = PropagandaMission(
            user_id=request.user_id,
            topic=request.topic,
            generation_result=generation_result,
            status="stage1" # Initial status
        )

        # 3. Save the mission to the database
        await propaganda_db.create_propaganda_mission(mission, db)

        # 4. Start background task for Stage 2
        background_tasks.add_task(generate_and_store_system_prompts, mission, db)

        # 5. Return the created mission object
        return mission

    except llm_service.LLMServiceError as e:
        raise HTTPException(status_code=502, detail=f"LLM service error: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")


@router.get("/mission_status/{mission_id}", response_model=PropagandaMission)
async def get_mission_status(
    mission_id: UUID,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Retrieves the current status and details of a propaganda mission.
    """
    mission = await propaganda_db.get_propaganda_mission_by_id(mission_id, db)
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")
    return mission