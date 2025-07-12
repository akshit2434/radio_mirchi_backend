from uuid import UUID
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.schemas.propaganda import PropagandaMission

async def get_propaganda_collection(db: AsyncIOMotorDatabase):
    return db.propaganda_missions

async def create_propaganda_mission(mission: PropagandaMission, db: AsyncIOMotorDatabase) -> PropagandaMission:
    """
    Inserts a new propaganda mission document into the database.
    """
    collection = await get_propaganda_collection(db)
    mission_dict = mission.model_dump()
    mission_dict["_id"] = mission.id
    await collection.insert_one(mission_dict)
    return mission

async def get_propaganda_mission_by_id(mission_id: UUID, db: AsyncIOMotorDatabase) -> PropagandaMission | None:
    """
    Retrieves a propaganda mission by its ID.
    """
    collection = await get_propaganda_collection(db)
    mission_data = await collection.find_one({"_id": mission_id})
    if mission_data:
        return PropagandaMission(**mission_data)
    return None

async def update_propaganda_mission(mission_id: UUID, data: dict, db: AsyncIOMotorDatabase) -> None:
    """
    Updates a propaganda mission in the database.
    """
    collection = await get_propaganda_collection(db)
    await collection.update_one({"_id": mission_id}, {"$set": data})