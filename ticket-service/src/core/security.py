import os
from fastapi import Header
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

load_dotenv()


INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY")
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("JWT_SECRET_KEY is not set in .env")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8  # 8 hours

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_minutes: int = ACCESS_TOKEN_EXPIRE_MINUTES) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    payload = decode_access_token(token)
    username, role, user_id = payload.get("sub"), payload.get("role"), payload.get("user_id")
    if username is None or role is None:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    return {"user_id": user_id, "username": username, "role": role}


def require_role(*allowed_roles: str):
    """Usage: Depends(require_role("admin", "support_engineer"))"""
    def role_checker(current_user: dict = Depends(get_current_user)) -> dict:
        if current_user["role"] not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{current_user['role']}' is not permitted to perform this action.",
            )
        return current_user
    return role_checker



def get_current_user_or_internal(
    x_internal_key: str = Header(None),
    token: str = Depends(OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)),
) -> dict:
    """
    Allows a route to be called EITHER by a logged-in user (JWT) OR by
    another internal service (doc-service) using a shared secret header.
    Used for endpoints doc-service needs to call without a real user session.
    """
    if x_internal_key and INTERNAL_API_KEY and x_internal_key == INTERNAL_API_KEY:
        return {"user_id": None, "username": "internal-service", "role": "internal"}

    if token is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    return get_current_user(token)