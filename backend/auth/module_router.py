from __future__ import annotations

from fastapi import APIRouter, Depends

from auth.db import get_db
from auth.jwt_utils import get_current_user
from auth.module_service import get_current_tenant_modules

router = APIRouter()


@router.get("/modules")
async def get_my_modules(user=Depends(get_current_user), db=Depends(get_db)):
    return await get_current_tenant_modules(db, user)
