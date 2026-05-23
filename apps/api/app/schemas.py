from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=256)


class AdminResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    email: str
