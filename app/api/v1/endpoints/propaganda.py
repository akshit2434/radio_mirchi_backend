import logging
import asyncio
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.schemas.propaganda import (
    PropagandaMission,
    PropagandaCreateRequest,
)
from app.services import llm_service
from app.db.mongodb_utils import get_database
from app.db import propaganda_db

router = APIRouter()

async def generate_and_store_unified_prompt(mission: PropagandaMission, db: AsyncIOMotorDatabase):
    """
    Background task (Stage 2): Generate the unified dialogue prompt and update the mission.
    """
    try:
        # Generate the dynamic part of the prompt
        dynamic_prompt = await asyncio.to_thread(
            llm_service.generate_unified_dialogue_prompt,
            mission_data=mission.generation_result,
            topic=mission.topic
        )

        # Prepare data for update
        update_data = {
            "dialogue_generator_prompt": dynamic_prompt,
            "status": "stage2"
        }

        # Update the mission in the database
        await propaganda_db.update_propaganda_mission(str(mission.id), update_data, db)

    except llm_service.LLMServiceError as e:
        logging.error(f"Stage 2 failed for mission {mission.id} due to LLMServiceError: {e}", exc_info=True)
        await propaganda_db.update_propaganda_mission(str(mission.id), {"status": "stage2_failed"}, db)
    except Exception as e:
        logging.error(f"Stage 2 failed for mission {mission.id} due to unexpected error: {e}", exc_info=True)
        await propaganda_db.update_propaganda_mission(str(mission.id), {"status": "stage2_failed"}, db)


@router.post("/create_mission", response_model=PropagandaMission, status_code=201)
async def create_mission(
    request: PropagandaCreateRequest,
    background_tasks: BackgroundTasks,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Creates a new propaganda mission (Stage 1).

    This endpoint synchronously generates the initial mission details,
    returns them, and then starts a background task to generate the unified
    dialogue prompt for all speakers (Stage 2).
    """
    try:
        # 1. Generate initial propaganda content (synchronous)
        generation_result = await asyncio.to_thread(
            llm_service.generate_initial_propaganda, topic=request.topic
        )

        # 2. Create the full mission object
        mission = PropagandaMission(
            user_id=request.user_id,
            topic=generation_result.topic, # Use the topic from the LLM response
            generation_result=generation_result,
            status="stage1" # Initial status
        )

        # 3. Save the mission to the database
        await propaganda_db.create_propaganda_mission(mission, db)

        # 4. Start background task for Stage 2
        background_tasks.add_task(generate_and_store_unified_prompt, mission, db)

        # 5. Return the created mission object
        return mission

    except llm_service.LLMServiceError as e:
        logging.exception(f"LLM service error during mission creation: {e}")
        raise HTTPException(status_code=502, detail=f"LLM service error: {e}")
    except Exception as e:
        logging.exception(f"An unexpected error occurred during mission creation: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")


@router.get("/mission_status/{mission_id}", response_model=PropagandaMission)
async def get_mission_status(
    mission_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Retrieves the current status and details of a propaganda mission.
    """
    mission = await propaganda_db.get_propaganda_mission_by_id(mission_id, db)
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")
    return mission