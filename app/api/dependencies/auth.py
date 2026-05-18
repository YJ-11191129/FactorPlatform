from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, HTTPException
from fastapi.security import APIKeyHeader

from app.core.settings import get_settings


@dataclass(frozen=True)
class Actor:
    key_id: str
    role: str


_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def _parse_api_keys(raw: str) -> dict[str, Actor]:
    out: dict[str, Actor] = {}
    for item in (raw or "").split(","):
        item = item.strip()
        if not item:
            continue
        parts = item.split(":", 1)
        if len(parts) != 2:
            continue
        key, role = parts[0].strip(), parts[1].strip()
        if not key or not role:
            continue
        out[key] = Actor(key_id=key[:6], role=role)
    return out


def get_actor(api_key: str | None = Depends(_api_key_header)) -> Actor | None:
    settings = get_settings()
    if not settings.require_auth and not settings.api_keys:
        return Actor(key_id="anonymous", role="admin")

    keys = _parse_api_keys(settings.api_keys)
    if not api_key:
        if settings.require_auth:
            raise HTTPException(status_code=401, detail="missing api key")
        return None

    actor = keys.get(api_key)
    if actor is None:
        raise HTTPException(status_code=401, detail="invalid api key")
    return actor


def require_role(*roles: str):
    role_set = set(roles)

    def _dep(actor: Actor | None = Depends(get_actor)) -> Actor:
        if actor is None:
            raise HTTPException(status_code=401, detail="missing api key")
        if actor.role not in role_set:
            raise HTTPException(status_code=403, detail="forbidden")
        return actor

    return _dep

