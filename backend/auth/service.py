from datetime import datetime, timedelta
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from backend.config import get_settings

settings = get_settings()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# Load physician credentials from environment variables
PHYSICIANS = {
    "dr.sharma": {
        "password_hash": settings.dr_sharma_password_hash,
        "physician_name": settings.dr_sharma_name,
        "department": settings.dr_sharma_department,
    },
    "dr.kumar": {
        "password_hash": settings.dr_kumar_password_hash,
        "physician_name": settings.dr_kumar_name,
        "department": settings.dr_kumar_department,
    },
    "dr.patel": {
        "password_hash": settings.dr_patel_password_hash,
        "physician_name": settings.dr_patel_name,
        "department": settings.dr_patel_department,
    },
}


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return pwd_context.verify(plain, hashed)
    except Exception:
        pass
    try:
        import bcrypt
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def authenticate_physician(username: str, password: str) -> Optional[dict]:
    physician = PHYSICIANS.get(username)
    if not physician or not verify_password(password, physician["password_hash"]):
        return None
    return {
        "username": username,
        "physician_name": physician["physician_name"],
        "department": physician["department"],
    }


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expires_at = datetime.utcnow() + timedelta(hours=settings.jwt_expire_hours)
    to_encode.update({"exp": expires_at})
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def verify_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        username = payload.get("sub") or payload.get("username")
        if not username or username not in PHYSICIANS:
            return None
        physician = PHYSICIANS[username]
        return {
            "username": username,
            "physician_name": physician["physician_name"],
            "department": physician["department"],
        }
    except JWTError:
        return None
