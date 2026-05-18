from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.settings import get_settings
from app.db.base import Base


_settings = get_settings()
_engine = create_engine(_settings.database_url, pool_pre_ping=True)
_SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=_engine)


def get_engine() -> Engine:
    return _engine


def init_db() -> None:
    import app.models

    Base.metadata.create_all(bind=_engine)


def get_db() -> Iterator[Session]:
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def db_session() -> Iterator[Session]:
    db = _SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

