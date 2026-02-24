"""routers/settings.py — Read and write user configuration from the meta table."""
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import SQLModel

from database.db import get_session
from models.meta import META_DEFAULTS, Meta

router = APIRouter(prefix="/api/settings", tags=["settings"])

_ALLOWED_KEYS = set(META_DEFAULTS.keys()) | {"jlpt_focus", "new_cards_per_day"}


class SettingUpdate(SQLModel):
    key: str
    value: Any  # Will be JSON-serialized before storage


@router.get("")
async def get_all_settings(db: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    """Return all meta rows as a key→deserialized-value dict."""
    result = await db.execute(select(Meta))
    rows = result.scalars().all()
    return {row.key: _safe_load(row.value) for row in rows}


@router.get("/{key}")
async def get_setting(key: str, db: AsyncSession = Depends(get_session)) -> Any:
    result = await db.execute(select(Meta).where(Meta.key == key))
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Setting '{key}' not found.")
    return {"key": key, "value": _safe_load(row.value)}


@router.post("")
async def upsert_setting(
    payload: SettingUpdate,
    db: AsyncSession = Depends(get_session),
) -> dict:
    if payload.key not in _ALLOWED_KEYS:
        raise HTTPException(
            status_code=400,
            detail=f"Key '{payload.key}' is not an editable setting. "
                   f"Allowed: {sorted(_ALLOWED_KEYS)}",
        )
    serialized = json.dumps(payload.value)
    result = await db.execute(select(Meta).where(Meta.key == payload.key))
    row = result.scalar_one_or_none()
    if row is None:
        db.add(Meta(key=payload.key, value=serialized))
    else:
        row.value = serialized
    return {"ok": True, "key": payload.key, "value": payload.value}


def _safe_load(raw: str) -> Any:
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return raw
