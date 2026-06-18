from pydantic import BaseModel, Field


class UserInput(BaseModel):
    text:str
    language:str

