from __future__ import annotations

import json
import os
import secrets
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, Optional

import pandas as pd


@dataclass(frozen=True)
class RunArtifact:
    calc_batch_id: str
    created_at: str
    factor_name: str
    mode: str
    universe: Optional[str]
    row_count: int
    parquet_path: str
    meta_path: str


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _runs_root() -> Path:
    return _select_runs_root()


@lru_cache(maxsize=1)
def _select_runs_root() -> Path:
    override = os.getenv("FACTOR_PLATFORM_RUNS_DIR")
    project_default = _project_root() / "data" / "exports" / "factor_runs"
    temp_base = Path(os.getenv("TEMP") or str(_project_root()))
    temp_default = temp_base / "FactorPlatformRuns"

    candidates = [Path(override)] if override else []
    candidates.extend([project_default, temp_default])

    for p in candidates:
        try:
            p.mkdir(parents=True, exist_ok=True)
            probe_dir = p / ".probe"
            probe_dir.mkdir(parents=True, exist_ok=True)
            probe_file = probe_dir / "write_test.txt"
            probe_file.write_text("ok", encoding="utf-8")
            probe_file.unlink(missing_ok=True)
            probe_dir.rmdir()
            return p
        except Exception:
            continue

    return temp_default


def _history_path() -> Path:
    return _runs_root() / "history.jsonl"


def new_calc_batch_id(prefix: str = "batch") -> str:
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
    rnd = secrets.token_hex(4)
    return f"{prefix}_{ts}_{rnd}"


def save_run(
    factor_name: str,
    mode: str,
    df: pd.DataFrame,
    params: Mapping[str, Any],
    universe: Optional[str] = None,
    provider_uri: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    calc_batch_id: Optional[str] = None,
) -> RunArtifact:
    runs_root = _runs_root()

    bid = calc_batch_id or new_calc_batch_id()
    created_at = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

    batch_dir = runs_root / bid
    batch_dir.mkdir(parents=True, exist_ok=True)

    parquet_path = batch_dir / "factor_values.parquet"
    meta_path = batch_dir / "meta.json"

    df.to_parquet(parquet_path, index=False)

    meta = {
        "calc_batch_id": bid,
        "created_at": created_at,
        "factor_name": factor_name,
        "mode": mode,
        "universe": universe,
        "provider_uri": provider_uri,
        "start_date": start_date,
        "end_date": end_date,
        "params": dict(params),
        "row_count": int(df.shape[0]),
        "columns": list(df.columns),
        "parquet_path": str(parquet_path),
        "meta_path": str(meta_path),
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")

    line = json.dumps(meta, ensure_ascii=False)
    history_path = runs_root / "history.jsonl"
    with history_path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")

    try:
        from app.services.research_ops_registry import register_factor_run_artifact

        register_factor_run_artifact(meta)
    except Exception:
        pass
    try:
        from app.services.artifact_service import register_artifact

        register_artifact(parquet_path, artifact_type="factor_values", run_id=bid, meta={"factor_name": factor_name, "mode": mode})
        register_artifact(meta_path, artifact_type="factor_run_metadata", run_id=bid, file_type="json")
    except Exception:
        pass

    return RunArtifact(
        calc_batch_id=bid,
        created_at=created_at,
        factor_name=factor_name,
        mode=mode,
        universe=universe,
        row_count=int(df.shape[0]),
        parquet_path=str(parquet_path),
        meta_path=str(meta_path),
    )


def list_runs(limit: int = 50) -> list[dict[str, Any]]:
    hp = _history_path()
    if not hp.exists():
        return []

    lines = hp.read_text(encoding="utf-8").splitlines()
    lines = lines[-max(int(limit), 0) :]

    out: list[dict[str, Any]] = []
    for line in reversed(lines):
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def get_run_meta(calc_batch_id: str) -> dict[str, Any]:
    mp = _runs_root() / calc_batch_id / "meta.json"
    return json.loads(mp.read_text(encoding="utf-8"))


def get_run_parquet_path(calc_batch_id: str) -> Path:
    return _runs_root() / calc_batch_id / "factor_values.parquet"
