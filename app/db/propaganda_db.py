from motor.motor_asyncio import AsyncIOMotorDatabase
from app.schemas.propaganda import PropagandaMission
from bson import ObjectId
from bson.errors import InvalidId

async def get_propaganda_collection(db: AsyncIOMotorDatabase):
    return db.missions

async def create_propaganda_mission(mission: PropagandaMission, db: AsyncIOMotorDatabase) -> PropagandaMission:
    """
    Inserts a new propaganda mission document into the database.
    """
    collection = await get_propaganda_collection(db)
    mission_dict = mission.model_dump(by_alias=True)
    await collection.insert_one(mission_dict)
    return mission

async def get_propaganda_mission_by_id(mission_id: str, db: AsyncIOMotorDatabase) -> PropagandaMission | None:
    """
    Retrieves a propaganda mission by its ID.
    """
    collection = await get_propaganda_collection(db)
    try:
        mission_data = await collection.find_one({"_id": ObjectId(mission_id)})
    except InvalidId:
        return None
    if mission_data:
        return PropagandaMission(**mission_data)
    return None

async def update_propaganda_mission(mission_id: str, data: dict, db: AsyncIOMotorDatabase) -> None:
    """
    Updates a propaganda mission in the database.
    """
    collection = await get_propaganda_collection(db)
    try:
        await collection.update_one({"_id": ObjectId(mission_id)}, {"$set": data})
    except InvalidId:
        # If the mission_id is not a valid ObjectId, the update cannot proceed.
        # This might indicate an attempt to update a non-existent or malformed ID.
        # Depending on desired behavior, you might log this or raise an HTTPException.
        # For now, we'll just let it pass silently as no update will occur.
        pass