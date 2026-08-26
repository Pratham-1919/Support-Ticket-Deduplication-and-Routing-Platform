from pydantic import BaseModel, Field


class UserRegisterRequest(BaseModel):
    username: str
    email: str
    password: str = Field(..., min_length=8)
    role: str = "reporter"


class UserOut(BaseModel):
    user_id: int
    username: str
    email: str
    role: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"