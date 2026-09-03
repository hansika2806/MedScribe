from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.errors import raise_standard_error
from backend.auth.service import verify_token


security = HTTPBearer(auto_error=False)


async def get_current_physician(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    if credentials is None:
        raise_standard_error("AUTH_EXPIRED")
    token = credentials.credentials
    physician = verify_token(token)
    if not physician:
        raise_standard_error("AUTH_EXPIRED")
    return physician
