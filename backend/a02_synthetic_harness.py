"""Shared synthetic-only auth harness for disposable local A02 acceptance.

Never import or configure this module in a shared/production deployment.
Actors are explicitly allowlisted by canonical user UUID; tenant UUID is separate.
"""
import json
import os

from fastapi import HTTPException, Request

from app import app
from auth.jwt_utils import get_current_user
from auth import document_router
from a02_synthetic_identity import resolve_synthetic_actor


def _actors() -> list[dict]:
    try:
        value = json.loads(os.environ["SYNTHETIC_ACTORS_JSON"])
    except (KeyError, json.JSONDecodeError) as exc:
        raise RuntimeError("SYNTHETIC_ACTORS_JSON must be configured in the isolated harness") from exc
    if not isinstance(value, list) or not value:
        raise RuntimeError("synthetic actor allowlist must be a non-empty list")
    return value


def _actor_from_token(token: str) -> dict:
    try:
        return resolve_synthetic_actor(token, _actors())
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


async def synthetic_user(request: Request) -> dict:
    authorization = request.headers.get("authorization", "")
    if not authorization.startswith("Bearer ") or authorization.count(" ") != 1:
        raise HTTPException(status_code=401, detail="Synthetic bearer token required")
    return _actor_from_token(authorization[7:])


async def synthetic_document_user(request: Request, token: str | None) -> dict:
    authorization = request.headers.get("authorization", "")
    raw_token = authorization[7:] if authorization.startswith("Bearer ") else token
    if not raw_token:
        raise HTTPException(status_code=401, detail="Synthetic bearer token required")
    return _actor_from_token(raw_token)


app.dependency_overrides[get_current_user] = synthetic_user
document_router._get_user_from_header_or_query = synthetic_document_user
