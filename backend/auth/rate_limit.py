import time
import os
from collections import defaultdict
from fastapi import Request, HTTPException, Depends
from .jwt_utils import get_current_user

# Configurable limits
API_RATE_LIMIT = int(os.getenv("API_RATE_LIMIT", "30"))        # requests per window
API_RATE_WINDOW = int(os.getenv("API_RATE_WINDOW", "60"))      # window in seconds
UPLOAD_RATE_LIMIT = int(os.getenv("UPLOAD_RATE_LIMIT", "5"))   # uploads per window
UPLOAD_RATE_WINDOW = int(os.getenv("UPLOAD_RATE_WINDOW", "60"))

class RateLimiter:
    def __init__(self):
        self._requests: dict[str, list[float]] = defaultdict(list)

    def check(self, key: str, limit: int, window: int):
        now = time.time()
        timestamps = self._requests[key]
        # Remove expired entries
        self._requests[key] = [t for t in timestamps if now - t < window]
        if len(self._requests[key]) >= limit:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Try again in {window}s.",
                headers={"Retry-After": str(window)},
            )
        self._requests[key].append(now)

_limiter = RateLimiter()

def _get_client_key(request: Request, user: dict | None = None) -> str:
    """Get rate limit key: user ID if authenticated, else IP."""
    if user and user.get("sub"):
        return f"user:{user['sub']}"
    forwarded = request.headers.get("X-Forwarded-For", "")
    ip = forwarded.split(",")[0].strip() if forwarded else request.client.host
    return f"ip:{ip}"

async def rate_limit_api(request: Request):
    """Rate limit dependency for API endpoints."""
    # Try to extract user from token (optional — don't fail if no token)
    user = None
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        try:
            from .jwt_utils import decode_token
            user = decode_token(auth[7:])
        except Exception:
            pass
    key = _get_client_key(request, user)
    _limiter.check(f"api:{key}", API_RATE_LIMIT, API_RATE_WINDOW)

async def rate_limit_upload(request: Request):
    """Stricter rate limit for upload endpoints."""
    user = None
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        try:
            from .jwt_utils import decode_token
            user = decode_token(auth[7:])
        except Exception:
            pass
    key = _get_client_key(request, user)
    _limiter.check(f"upload:{key}", UPLOAD_RATE_LIMIT, UPLOAD_RATE_WINDOW)


async def rate_limit_data_export(request: Request):
    """Heavily-throttled limit for GDPR/PDPL data exports.

    Defaults: 3 exports per hour per user. Tunable via env so tests can
    relax this without monkey-patching.
    """
    limit = int(os.getenv("DATA_EXPORT_LIMIT", "3"))
    window = int(os.getenv("DATA_EXPORT_WINDOW", "3600"))
    user = None
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        try:
            from .jwt_utils import decode_token
            user = decode_token(auth[7:])
        except Exception:
            pass
    key = _get_client_key(request, user)
    _limiter.check(f"data_export:{key}", limit, window)
