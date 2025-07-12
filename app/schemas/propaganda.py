from pydantic import BaseModel, Field
from typing import List

class Speaker(BaseModel):
    name: str
    gender: str
    color: str = Field(description="a unique colour for this speaker that goes well on a light beige background. in hexcode example:'#AC3A3A', '#34BF50', '#9C61B3'")
    description: str = Field(description="a short description of the speaker, their background, and their role in the radio brodcast. example: 'John Doe is a seasoned journalist with a passion for uncovering the truth. He himself is brainwashed and uses critical thinking to push the propanda.'")

class PropagandaCreate(BaseModel):
    topic: str = Field(..., examples=["The benefits of a new government surveillance program"])

class Propaganda(BaseModel):
    summary: str
    proof_sentences: List[str] = Field(..., min_length=1, max_length=5)
    speakers: List[Speaker] = Field(..., min_length=1, max_length=4)
    initial_listeners: int
    awakened_listeners: int = 0