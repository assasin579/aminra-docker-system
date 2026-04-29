import os
import json as _json
import time as _time
from datetime import datetime, timedelta, timezone
from pathlib import Path as _Path
from typing import Optional
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

SECRET = os.getenv("JWT_SECRET")
if not SECRET:
    raise RuntimeError("JWT_SECRET environment variable is required")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
EXPIRE_H = int(os.getenv("JWT_EXPIRE_HOURS", "8"))
REFRESH_EXPIRE_DAYS = int(os.getenv("JWT_REFRESH_DAYS", "7"))

_bearer = HTTPBearer(auto_error=False)

ADMIN_EMAIL = "admin@aminra.com"

# Old-admin session file written by /admin/login in app.py
_ADMIN_SESSIONS_FILE = _Path("data/admin_sessions.json")


def _validate_old_admin_session(token: str) -> bool:
    try:
        if not _ADMIN_SESSIONS_FILE.exists():
            return False
        sessions = _json.loads(_ADMIN_SESSIONS_FILE.read_text())
        exp = sessions.get(token)
        return bool(exp and _time.time() <= exp)
    except Exception:
        return False


def create_access_token(data: dict, expires_hours: Optional[int] = None) -> str:
    payload = data.copy()
    exp = datetime.now(timezone.utc) + timedelta(hours=expires_hours or EXPIRE_H)
    payload.update({"exp": exp})
    return jwt.encode(payload, SECRET, algorithm=ALGORITHM)


def create_refresh_token(data: dict) -> str:
    payload = data.copy()
    exp = datetime.now(timezone.utc) + timedelta(days=REFRESH_EXPIRE_DAYS)
    payload.update({"exp": exp, "type": "refresh"})
    return jwt.encode(payload, SECRET, algorithm=ALGORITHM)


def decode_refresh_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token is not a refresh token")
    return payload


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")


from fastapi import Request


def get_current_user(
    request: Request,
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> dict:
    if creds:
        return decode_token(creds.credentials)
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")


def require_business_owner(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "business" or not user.get("is_owner"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Business owner access required")
    return user


def require_provider_owner(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "provider" or not user.get("is_owner"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Provider owner access required")
    return user


def require_active_user(user: dict = Depends(get_current_user)) -> dict:
    if user.get("status") != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account not active")
    return user


async def require_admin(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> dict:
    """Accept either a JWT user token (admin email + provider role) or the
    opaque session token from /admin/login. Returns a user-shaped dict.

    Falling back to the old-admin session keeps the /admin UI working with
    routes registered under /api/auth/admin/* (analytics, audit-logs, etc.)
    while a single backend dependency continues to gate access.
    """
    if not creds:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    token = creds.credentials

    try:
        user = jwt.decode(token, SECRET, algorithms=[ALGORITHM])
        if user.get("email") == ADMIN_EMAIL and user.get("role") == "provider":
            return user
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    except JWTError:
        pass

    if not _validate_old_admin_session(token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")

    from auth.db import get_pool

    pool = get_pool()
    async with pool.acquire() as db:
        row = await db.fetchrow(
            "SELECT id, email, role FROM users WHERE email = $1",
            ADMIN_EMAIL,
        )
    if not row:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin user record missing — run admin bootstrap",
        )
    return {
        "sub": str(row["id"]),
        "email": row["email"],
        "role": row["role"] or "provider",
        "is_owner": True,
    }
