from pydantic import BaseModel, Field
#defines structure of input and output data

class UserRequest(BaseModel):
    input:str = Field(...,description="User's text input")

class ProcessResponse(BaseModel):
    text:str
    audio:str | None = None
    type:str 


