from fastapi import APIRouter, Depends

from backend.auth.dependency import get_current_physician
from backend.auth.models import LoginRequest, PhysicianInfo, TokenResponse
from backend.auth.service import authenticate_physician, create_access_token
from backend.errors import raise_standard_error


router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest):
    physician = authenticate_physician(payload.username, payload.password)
    if not physician:
        raise_standard_error("AUTH_INVALID")
    token = create_access_token({"sub": physician["username"]})
    return TokenResponse(
        access_token=token,
        physician_name=physician["physician_name"],
        username=physician["username"],
    )


@router.get("/me", response_model=PhysicianInfo)
async def me(current_physician: dict = Depends(get_current_physician)):
    return PhysicianInfo(**current_physician)


@router.get("/logout")
async def logout():
    return {"status": "logged_out"}
