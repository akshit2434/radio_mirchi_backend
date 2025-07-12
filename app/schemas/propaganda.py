from pydantic import BaseModel, Field
from typing import List

class Speaker(BaseModel):
    name: str
    gender: str

class PropagandaCreate(BaseModel):
    topic: str = Field(..., examples=["The benefits of a new government surveillance program"])

class Propaganda(BaseModel):
    summary: str
    speakers: List[Speaker] = Field(..., min_length=1, max_length=4)
    initial_listeners: int
    awakened_listeners: int = 0