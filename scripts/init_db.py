from __future__ import annotations

import sys
from pathlib import Path

from alembic import command
from alembic.config import Config

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import db_session
from app.services.factor_metadata_service import sync_code_factor_metadata


def main() -> None:
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")
    with db_session() as db:
        sync_code_factor_metadata(db)

if __name__ == "__main__":
    main()
