from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from app.services.regime_engine import (
    get_breakpoints_items,
    get_event_library,
    get_regime_artifacts,
    refresh_regime_artifacts,
)


def _set_env(penalty: int, min_size: int, jump: int = 1) -> None:
    os.environ["FACTOR_PLATFORM_REGIME_PENALTY"] = str(penalty)
    os.environ["FACTOR_PLATFORM_REGIME_MIN_SIZE"] = str(min_size)
    os.environ["FACTOR_PLATFORM_REGIME_JUMP"] = str(jump)


def _score(rows_snapshot: int, rows_breakpoints: int, primary_hit: int, secondary_hit: int, avg_segment_len: float) -> float:
    # Higher is better.
    hit_score = 3.0 * primary_hit + 2.0 * secondary_hit
    density_penalty = rows_breakpoints / max(1.0, rows_snapshot) * 100.0
    seg_bonus = min(0.5, avg_segment_len / 100.0)
    return float(hit_score - density_penalty + seg_bonus)


def _summarize_case(penalty: int, min_size: int, jump: int = 1) -> dict[str, Any]:
    _set_env(penalty=penalty, min_size=min_size, jump=jump)
    s, _ = refresh_regime_artifacts()
    items = get_breakpoints_items()

    primary_hit = sum(1 for x in items if x.get("event_hit_type") == "PRIMARY_SHOCK_HIT")
    secondary_hit = sum(1 for x in items if x.get("event_hit_type") == "SECONDARY_TRANSITION_HIT")
    total_hit = sum(1 for x in items if x.get("event_hit_flag"))
    rows_snapshot = len(s)
    rows_breakpoints = len(items)
    avg_segment_len = rows_snapshot / max(1, rows_breakpoints)
    density_per_100 = rows_breakpoints / max(1.0, rows_snapshot) * 100.0
    sc = _score(rows_snapshot, rows_breakpoints, primary_hit, secondary_hit, avg_segment_len)

    latest = s.iloc[-1].to_dict() if not s.empty else {}
    return {
        "penalty": penalty,
        "min_size": min_size,
        "jump": jump,
        "rows_snapshot": rows_snapshot,
        "rows_breakpoints": rows_breakpoints,
        "breakpoints_per_100": density_per_100,
        "avg_segment_len": avg_segment_len,
        "primary_hit": primary_hit,
        "secondary_hit": secondary_hit,
        "total_hit": total_hit,
        "score": sc,
        "latest_regime": latest.get("regime_label"),
        "latest_risk": latest.get("market_risk_level"),
    }


def main() -> None:
    out_dir = Path("D:/FactorPlatform/data/exports/regime_engine")
    out_dir.mkdir(parents=True, exist_ok=True)

    # Matrix from review document.
    matrix = [
        (12, 20, 1),
        (15, 20, 1),
        (10, 25, 1),
        (12, 25, 1),
        (15, 25, 1),
        (12, 30, 1),
    ]

    event_lib = get_event_library()
    rows = [_summarize_case(p, m, j) for p, m, j in matrix]
    rows = sorted(rows, key=lambda x: x["score"], reverse=True)

    payload = {
        "event_library": event_lib,
        "cases": rows,
        "best_case": rows[0] if rows else None,
    }
    (out_dir / "regime_tuning_matrix_v2.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    md = []
    md.append("# REGIME_TUNING_MATRIX_V2_RESULT")
    md.append("")
    md.append("## Event Library")
    md.append("")
    md.append(f"- primary_shocks: `{event_lib['primary_shocks']}`")
    md.append(f"- secondary_transitions: `{event_lib['secondary_transitions']}`")
    md.append("")
    md.append("## Ranked Cases")
    md.append("")
    for i, r in enumerate(rows, start=1):
        md.append(
            f"{i}. penalty={r['penalty']}, min_size={r['min_size']}, jump={r['jump']}, "
            f"breakpoints={r['rows_breakpoints']}, density={r['breakpoints_per_100']:.2f}/100, "
            f"primary={r['primary_hit']}, secondary={r['secondary_hit']}, score={r['score']:.3f}"
        )
    md.append("")
    if rows:
        b = rows[0]
        md.append("## Recommended Baseline")
        md.append("")
        md.append(f"- `penalty={b['penalty']}`")
        md.append(f"- `min_size={b['min_size']}`")
        md.append(f"- `jump={b['jump']}`")
        md.append(f"- `breakpoints={b['rows_breakpoints']}`")
        md.append(f"- `primary_hit={b['primary_hit']}`, `secondary_hit={b['secondary_hit']}`")
    (out_dir / "regime_tuning_matrix_v2.md").write_text("\n".join(md), encoding="utf-8")

    print(json.dumps({"ok": True, "best_case": rows[0] if rows else None}, ensure_ascii=False))


if __name__ == "__main__":
    main()

