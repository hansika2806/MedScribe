from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    physician_name: str
    username: str


class PhysicianInfo(BaseModel):
    username: str
    physician_name: str
    department: str
