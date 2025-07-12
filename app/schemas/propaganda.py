from pydantic import BaseModel, Field
from typing import List

class Speaker(BaseModel):
    name: str
    gender: str
    color: str = Field(description="a unique colour for this speaker that goes well on a light beige background. in hexcode example:'#AC3A3A', '#34BF50', '#9C61B3'")

class PropagandaCreate(BaseModel):
    topic: str = Field(..., examples=["The benefits of a new government surveillance program"])

class Propaganda(BaseModel):
    summary: str
    speakers: List[Speaker] = Field(..., min_length=1, max_length=4)
    initial_listeners: int
    # awakened_listeners: int = 0