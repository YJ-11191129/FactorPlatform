from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import pandas as pd


QUALITY_STATUSES = {"PASS", "WARN", "FAIL", "NOT_TESTED"}


@dataclass(frozen=True)
class QualityThresholds:
    min_coverage: float = 0.70
    max_missing_rate: float = 0.30
    min_date_count: int = 40
    min_rank_ic_mean: float = 0.01
    min_positive_ic_ratio: float = 0.52
    min_monotonicity: float = 0.15
    suspicious_abs_ic: float = 0.25

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any] | None = None) -> "QualityThresholds":
        data = dict(raw or {})
        fields = cls.__dataclass_fields__
        clean: dict[str, Any] = {}
        for key in fields:
            if key in data and data[key] is not None:
                clean[key] = data[key]
        return cls(**clean)

    def as_dict(self) -> dict[str, Any]:
        return {
            "min_coverage": self.min_coverage,
            "max_missing_rate": self.max_missing_rate,
            "min_date_count": self.min_date_count,
            "min_rank_ic_mean": self.min_rank_ic_mean,
            "min_positive_ic_ratio": self.min_positive_ic_ratio,
            "min_monotonicity": self.min_monotonicity,
            "suspicious_abs_ic": self.suspicious_abs_ic,
        }


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def quality_root() -> Path:
    root = Path(os.getenv("FACTOR_PLATFORM_RESEARCH_QUALITY_DIR", str(_project_root() / "data" / "exports" / "research_quality")))
    root.mkdir(parents=True, exist_ok=True)
    return root


def _quality_dir(source_run_id: str) -> Path:
    path = quality_root() / _safe_id(source_run_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _quality_report_path(source_run_id: str) -> Path:
    return _quality_dir(source_run_id) / "quality_report.json"


def _quality_findings_path(source_run_id: str) -> Path:
    return _quality_dir(source_run_id) / "quality_findings.jsonl"


def _history_path() -> Path:
    return quality_root() / "history.jsonl"


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_id(value: Any) -> str:
    text = str(value or "").strip()
    out = []
    for ch in text:
        out.append(ch if ch.isalnum() or ch in {"_", "-", "."} else "_")
    return "".join(out).strip("_") or "unknown"


def _safe_float(value: Any) -> float | None:
    try:
        out = float(value)
    except Exception:
        return None
    return out if math.isfinite(out) else None


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, (date, datetime, pd.Timestamp)):
        return str(value)
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    try:
        import numpy as np

        if isinstance(value, (np.integer,)):
            return int(value)
        if isinstance(value, (np.floating,)):
            number = float(value)
            return number if math.isfinite(number) else None
    except Exception:
        pass
    return value


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_json_safe(dict(payload)), ensure_ascii=False, indent=2), encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _append_jsonl(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_json_safe(dict(payload)), ensure_ascii=False) + "\n")


def _status_rank(status: str) -> int:
    return {"PASS": 0, "NOT_TESTED": 1, "WARN": 2, "FAIL": 3}.get(status, 2)


def _overall_status(checks: list[dict[str, Any]]) -> str:
    if any(check.get("status") == "FAIL" for check in checks):
        return "FAIL"
    if any(check.get("status") in {"WARN", "NOT_TESTED"} for check in checks):
        return "WARN"
    return "PASS"


def _quality_score(checks: list[dict[str, Any]]) -> float:
    score = 100.0
    for check in checks:
        status = str(check.get("status") or "WARN")
        if status == "FAIL":
            score -= 30.0
        elif status == "WARN":
            score -= 12.0
        elif status == "NOT_TESTED":
            score -= 5.0
    return round(max(0.0, score), 2)


def _promotion_status(quality_status: str) -> str:
    if quality_status == "PASS":
        return "PRODUCTION_CANDIDATE"
    if quality_status == "WARN":
        return "SHADOW_REVIEW"
    return "SHADOW_ONLY"


def _check(
    check_id: str,
    status: str,
    reason_code: str,
    message: str,
    evidence: Mapping[str, Any] | None = None,
    threshold: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if status not in QUALITY_STATUSES:
        status = "WARN"
    return {
        "check_id": check_id,
        "status": status,
        "reason_code": reason_code,
        "message": message,
        "evidence": dict(evidence or {}),
        "threshold": dict(threshold or {}),
    }


def _native_qlib_mining_dir(source_run_id: str) -> Path:
    from app.services.native_qlib_research_service import _research_root

    return _research_root() / "factor_mining" / source_run_id


def _load_mining_artifacts(source_run_id: str) -> dict[str, Any]:
    run_dir = _native_qlib_mining_dir(source_run_id)
    summary_path = run_dir / "summary.json"
    if not summary_path.exists():
        raise FileNotFoundError(f"factor mining summary not found: {source_run_id}")
    summary = _read_json(summary_path)
    artifacts = summary.get("artifacts") if isinstance(summary.get("artifacts"), Mapping) else {}

    def parquet(name: str, fallback: str) -> pd.DataFrame:
        path = Path(str(artifacts.get(name) or run_dir / fallback))
        if not path.exists():
            return pd.DataFrame()
        return pd.read_parquet(path)

    return {
        "run_dir": run_dir,
        "summary": summary,
        "panel": parquet("factor_panel", "factor_panel.parquet"),
        "ranking": parquet("factor_ranking", "factor_ranking.parquet"),
        "ic_series": parquet("ic_series", "ic_series.parquet"),
        "group_returns": parquet("group_returns", "group_returns.parquet"),
    }


def _timing_checks(panel: pd.DataFrame) -> list[dict[str, Any]]:
    if panel.empty:
        return [
            _check(
                "timing_alignment",
                "NOT_TESTED",
                "TIMING_PANEL_MISSING",
                "Factor panel is missing; cannot verify trade_date < entry_trade_date <= exit_trade_date.",
            )
        ]
    needed = {"trade_date", "entry_trade_date", "exit_trade_date"}
    missing = sorted(needed - set(panel.columns))
    if missing:
        return [
            _check(
                "timing_alignment",
                "NOT_TESTED",
                "TIMING_METADATA_MISSING",
                "Timing metadata is missing; v1 cannot prove next-day executable alignment.",
                evidence={"missing_columns": missing},
            )
        ]
    work = panel[list(needed)].copy()
    for col in needed:
        work[col] = pd.to_datetime(work[col], errors="coerce")
    invalid_dates = int(work[list(needed)].isna().any(axis=1).sum())
    bad_entry = work[work["entry_trade_date"] <= work["trade_date"]]
    bad_exit = work[work["exit_trade_date"] < work["entry_trade_date"]]
    if invalid_dates or not bad_entry.empty or not bad_exit.empty:
        return [
            _check(
                "timing_alignment",
                "FAIL",
                "TIMING_LEAKAGE_RISK",
                "Timing alignment failed; factor values must be formed at t close and traded no earlier than t+1.",
                evidence={
                    "row_count": int(panel.shape[0]),
                    "invalid_date_rows": invalid_dates,
                    "entry_not_after_trade_rows": int(bad_entry.shape[0]),
                    "exit_before_entry_rows": int(bad_exit.shape[0]),
                    "bad_entry_sample": bad_entry.head(3).astype(str).to_dict(orient="records"),
                },
            )
        ]
    return [
        _check(
            "timing_alignment",
            "PASS",
            "TIMING_ALIGNMENT_PASS",
            "All sampled rows satisfy trade_date < entry_trade_date <= exit_trade_date.",
            evidence={"row_count": int(panel.shape[0])},
        )
    ]


def _ranking_checks(ranking: pd.DataFrame, thresholds: QualityThresholds) -> tuple[list[dict[str, Any]], dict[str, str]]:
    checks: list[dict[str, Any]] = []
    factor_status: dict[str, str] = {}
    if ranking.empty:
        return [
            _check(
                "factor_ranking_available",
                "FAIL",
                "FACTOR_RANKING_MISSING",
                "Factor ranking artifact is missing; quality cannot be evaluated.",
            )
        ], factor_status

    for _, row in ranking.iterrows():
        factor = str(row.get("factor_name") or "UNKNOWN")
        factor_checks: list[dict[str, Any]] = []
        coverage = _safe_float(row.get("coverage"))
        missing_rate = _safe_float(row.get("missing_rate"))
        date_count = int(_safe_float(row.get("date_count")) or 0)
        rank_ic = _safe_float(row.get("rank_ic_mean"))
        ic = _safe_float(row.get("ic_mean"))
        positive_ic = _safe_float(row.get("positive_ic_ratio"))
        monotonicity = _safe_float(row.get("monotonicity"))
        long_short = _safe_float(row.get("long_short_mean"))

        if coverage is None or missing_rate is None:
            factor_checks.append(
                _check(
                    "coverage",
                    "NOT_TESTED",
                    "COVERAGE_METADATA_MISSING",
                    f"{factor}: coverage metadata is missing.",
                    evidence={"factor_name": factor},
                )
            )
        elif coverage < thresholds.min_coverage or missing_rate > thresholds.max_missing_rate:
            factor_checks.append(
                _check(
                    "coverage",
                    "FAIL",
                    "FACTOR_COVERAGE_FAIL",
                    f"{factor}: coverage or missing-rate threshold failed.",
                    evidence={"factor_name": factor, "coverage": coverage, "missing_rate": missing_rate},
                    threshold={"min_coverage": thresholds.min_coverage, "max_missing_rate": thresholds.max_missing_rate},
                )
            )
        else:
            factor_checks.append(
                _check(
                    "coverage",
                    "PASS",
                    "FACTOR_COVERAGE_PASS",
                    f"{factor}: coverage is sufficient.",
                    evidence={"factor_name": factor, "coverage": coverage, "missing_rate": missing_rate},
                )
            )

        if date_count < max(10, thresholds.min_date_count // 2):
            factor_checks.append(
                _check(
                    "sample_stability",
                    "FAIL",
                    "DATE_COUNT_TOO_LOW",
                    f"{factor}: date_count is too low for stable validation.",
                    evidence={"factor_name": factor, "date_count": date_count},
                    threshold={"min_date_count": thresholds.min_date_count},
                )
            )
        elif date_count < thresholds.min_date_count:
            factor_checks.append(
                _check(
                    "sample_stability",
                    "WARN",
                    "DATE_COUNT_WARN",
                    f"{factor}: date_count is below the preferred validation threshold.",
                    evidence={"factor_name": factor, "date_count": date_count},
                    threshold={"min_date_count": thresholds.min_date_count},
                )
            )
        else:
            factor_checks.append(
                _check(
                    "sample_stability",
                    "PASS",
                    "DATE_COUNT_PASS",
                    f"{factor}: date_count is sufficient.",
                    evidence={"factor_name": factor, "date_count": date_count},
                )
            )

        if rank_ic is None or positive_ic is None:
            factor_checks.append(
                _check(
                    "rank_ic_stability",
                    "NOT_TESTED",
                    "RANK_IC_METADATA_MISSING",
                    f"{factor}: RankIC stability metadata is missing.",
                    evidence={"factor_name": factor},
                )
            )
        elif rank_ic < thresholds.min_rank_ic_mean:
            factor_checks.append(
                _check(
                    "rank_ic_stability",
                    "FAIL",
                    "LOW_RANK_IC",
                    f"{factor}: RankIC is below the promotion threshold.",
                    evidence={"factor_name": factor, "rank_ic_mean": rank_ic, "positive_ic_ratio": positive_ic},
                    threshold={"min_rank_ic_mean": thresholds.min_rank_ic_mean, "min_positive_ic_ratio": thresholds.min_positive_ic_ratio},
                )
            )
        elif positive_ic < thresholds.min_positive_ic_ratio:
            factor_checks.append(
                _check(
                    "rank_ic_stability",
                    "WARN",
                    "LOW_POSITIVE_IC_RATIO",
                    f"{factor}: positive IC ratio is below the stability threshold.",
                    evidence={"factor_name": factor, "rank_ic_mean": rank_ic, "positive_ic_ratio": positive_ic},
                    threshold={"min_positive_ic_ratio": thresholds.min_positive_ic_ratio},
                )
            )
        else:
            factor_checks.append(
                _check(
                    "rank_ic_stability",
                    "PASS",
                    "RANK_IC_STABILITY_PASS",
                    f"{factor}: RankIC level and positive-ratio pass.",
                    evidence={"factor_name": factor, "rank_ic_mean": rank_ic, "positive_ic_ratio": positive_ic},
                )
            )

        if long_short is None or monotonicity is None:
            factor_checks.append(
                _check(
                    "group_return_monotonicity",
                    "NOT_TESTED",
                    "GROUP_RETURN_METADATA_MISSING",
                    f"{factor}: group return or monotonicity metadata is missing.",
                    evidence={"factor_name": factor},
                )
            )
        elif long_short <= 0:
            factor_checks.append(
                _check(
                    "group_return_monotonicity",
                    "FAIL",
                    "LONG_SHORT_REVERSED",
                    f"{factor}: long-short spread is not positive.",
                    evidence={"factor_name": factor, "long_short_mean": long_short, "monotonicity": monotonicity},
                )
            )
        elif monotonicity < thresholds.min_monotonicity:
            factor_checks.append(
                _check(
                    "group_return_monotonicity",
                    "WARN",
                    "GROUP_RETURN_MONOTONICITY_WEAK",
                    f"{factor}: group-return monotonicity is weak.",
                    evidence={"factor_name": factor, "long_short_mean": long_short, "monotonicity": monotonicity},
                    threshold={"min_monotonicity": thresholds.min_monotonicity},
                )
            )
        else:
            factor_checks.append(
                _check(
                    "group_return_monotonicity",
                    "PASS",
                    "GROUP_RETURN_MONOTONICITY_PASS",
                    f"{factor}: group-return spread and monotonicity pass.",
                    evidence={"factor_name": factor, "long_short_mean": long_short, "monotonicity": monotonicity},
                )
            )

        high_ic_values = [x for x in [ic, rank_ic] if x is not None and abs(x) > thresholds.suspicious_abs_ic]
        if high_ic_values:
            factor_checks.append(
                _check(
                    "suspicious_ic",
                    "WARN",
                    "SUSPICIOUSLY_HIGH_IC",
                    f"{factor}: IC/RankIC is unusually high; inspect for look-ahead or label leakage.",
                    evidence={"factor_name": factor, "ic_mean": ic, "rank_ic_mean": rank_ic},
                    threshold={"suspicious_abs_ic": thresholds.suspicious_abs_ic},
                )
            )
        else:
            factor_checks.append(
                _check(
                    "suspicious_ic",
                    "PASS",
                    "IC_RANGE_PASS",
                    f"{factor}: IC magnitude is not suspiciously high.",
                    evidence={"factor_name": factor, "ic_mean": ic, "rank_ic_mean": rank_ic},
                )
            )

        status = _overall_status(factor_checks)
        factor_status[factor] = status
        checks.extend(factor_checks)
    return checks, factor_status


def _reason_codes(checks: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    for check in checks:
        if check.get("status") == "PASS":
            continue
        code = str(check.get("reason_code") or "")
        if code and code not in out:
            out.append(code)
    return out


def _register_quality_report(report: Mapping[str, Any]) -> str | None:
    try:
        from app.services.research_ops_registry import _safe_id, upsert_object

        source_run_id = str(report.get("source_run_id"))
        status_map = {"PASS": "OK", "WARN": "WARN", "FAIL": "BLOCKED"}
        obj = upsert_object(
            object_id=f"validation_result_quality_{_safe_id(source_run_id)}",
            object_type="validation_result",
            status=status_map.get(str(report.get("quality_status")), "WARN"),
            asof_date=str(report.get("asof_date") or report.get("evaluated_at") or "")[:10],
            created_at=str(report.get("evaluated_at") or _now_iso()),
            source_system="research_quality_guard",
            source_run_id=source_run_id,
            artifact_paths=[report.get("artifact_path"), report.get("findings_path")],
            summary={
                "source_type": report.get("source_type"),
                "source_run_id": source_run_id,
                "quality_status": report.get("quality_status"),
                "quality_score": report.get("quality_score"),
                "promotion_status": report.get("promotion_status"),
                "not_executable": report.get("not_executable"),
                "reason_codes": report.get("reason_codes") or [],
                "factor_status": report.get("factor_status") or {},
                "timing_note": report.get("timing_note"),
            },
            parents=[f"factor_run_{_safe_id(source_run_id)}", f"validation_result_{_safe_id(source_run_id)}"],
            tags=["research_quality", str(report.get("quality_status") or "WARN").lower()],
            external_ids=[source_run_id, *(report.get("reason_codes") or [])],
        )
        return str(obj.get("object_id"))
    except Exception:
        return None


def evaluate_research_quality(
    *,
    source_run_id: str,
    source_type: str = "qlib_factor_mining",
    thresholds: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if source_type != "qlib_factor_mining":
        raise ValueError("source_type must be qlib_factor_mining in v1")
    limits = QualityThresholds.from_mapping(thresholds)
    artifacts = _load_mining_artifacts(source_run_id)
    summary = artifacts["summary"]
    panel = artifacts["panel"]
    ranking = artifacts["ranking"]
    evaluated_at = _now_iso()

    checks: list[dict[str, Any]] = []
    checks.extend(_timing_checks(panel))
    ranking_checks, factor_status = _ranking_checks(ranking, limits)
    checks.extend(ranking_checks)
    checks = sorted(checks, key=lambda c: (_status_rank(str(c.get("status"))), str(c.get("check_id"))), reverse=True)
    status = _overall_status(checks)
    reasons = _reason_codes(checks)
    report_dir = _quality_dir(source_run_id)
    report_path = report_dir / "quality_report.json"
    findings_path = report_dir / "quality_findings.jsonl"
    report = {
        "source_type": source_type,
        "source_run_id": source_run_id,
        "evaluated_at": evaluated_at,
        "asof_date": (summary.get("date_range") or {}).get("end_date") if isinstance(summary.get("date_range"), Mapping) else evaluated_at[:10],
        "quality_status": status,
        "quality_score": _quality_score(checks),
        "promotion_status": _promotion_status(status),
        "not_executable": status == "FAIL",
        "reason_codes": reasons,
        "checks": checks,
        "factor_status": factor_status,
        "thresholds": limits.as_dict(),
        "artifact_path": str(report_path),
        "findings_path": str(findings_path),
        "source_artifact_path": str(artifacts["run_dir"]),
        "timing_note": "Factor values are observed at t close; executable validation requires trade_date < entry_trade_date <= exit_trade_date.",
        "research_ops_object_id": None,
    }

    _write_json(report_path, report)
    findings_path.write_text("", encoding="utf-8")
    for check in checks:
        if check.get("status") != "PASS":
            _append_jsonl(findings_path, check)
    object_id = _register_quality_report(report)
    report["research_ops_object_id"] = object_id
    _write_json(report_path, report)
    _append_jsonl(_history_path(), {k: report.get(k) for k in ["source_type", "source_run_id", "evaluated_at", "quality_status", "quality_score", "promotion_status", "not_executable", "reason_codes", "artifact_path", "research_ops_object_id"]})
    return report


def read_quality_report(source_run_id: str) -> dict[str, Any]:
    path = _quality_report_path(source_run_id)
    if not path.exists():
        raise FileNotFoundError(f"quality report not found: {source_run_id}")
    return _read_json(path)


def try_read_quality_report(source_run_id: str) -> dict[str, Any] | None:
    try:
        return read_quality_report(source_run_id)
    except FileNotFoundError:
        return None


def list_quality_runs(limit: int = 50) -> list[dict[str, Any]]:
    path = _history_path()
    if not path.exists():
        rows = []
        for report_path in sorted(quality_root().glob("*/quality_report.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                report = _read_json(report_path)
                rows.append({k: report.get(k) for k in ["source_type", "source_run_id", "evaluated_at", "quality_status", "quality_score", "promotion_status", "not_executable", "reason_codes", "artifact_path", "research_ops_object_id"]})
            except Exception:
                continue
        return rows[: max(0, int(limit))]
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for line in reversed(path.read_text(encoding="utf-8").splitlines()):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        key = str(row.get("source_run_id") or "")
        if key in seen:
            continue
        seen.add(key)
        rows.append(row)
        if len(rows) >= max(0, int(limit)):
            break
    return rows


def summarize_quality_for_portfolio(mining_run_id: str, selected_factors: list[str]) -> dict[str, Any]:
    report = try_read_quality_report(mining_run_id)
    if not report:
        return {
            "quality_gate": None,
            "promotion_status": "SHADOW_ONLY",
            "not_executable": True,
            "quality_reason_codes": ["QUALITY_REPORT_MISSING"],
        }
    factor_status = report.get("factor_status") if isinstance(report.get("factor_status"), Mapping) else {}
    missing = [factor for factor in selected_factors if factor not in factor_status]
    failing = [factor for factor in selected_factors if factor_status.get(factor) == "FAIL"]
    warn = [factor for factor in selected_factors if factor_status.get(factor) == "WARN"]
    reason_codes = list(report.get("reason_codes") or [])
    if missing and "QUALITY_FACTOR_STATUS_MISSING" not in reason_codes:
        reason_codes.append("QUALITY_FACTOR_STATUS_MISSING")
    if failing and "QUALITY_FACTOR_FAIL" not in reason_codes:
        reason_codes.append("QUALITY_FACTOR_FAIL")
    if missing or failing:
        promotion = "SHADOW_ONLY"
        not_executable = True
    elif warn or report.get("quality_status") == "WARN":
        promotion = "SHADOW_REVIEW"
        not_executable = False
    else:
        promotion = "PRODUCTION_CANDIDATE"
        not_executable = False
    quality_gate = {
        "source_run_id": report.get("source_run_id"),
        "quality_status": report.get("quality_status"),
        "quality_score": report.get("quality_score"),
        "promotion_status": report.get("promotion_status"),
        "reason_codes": report.get("reason_codes") or [],
        "research_ops_object_id": report.get("research_ops_object_id"),
        "artifact_path": report.get("artifact_path"),
        "factor_status": {factor: factor_status.get(factor, "MISSING") for factor in selected_factors},
    }
    return {
        "quality_gate": quality_gate,
        "promotion_status": promotion,
        "not_executable": not_executable,
        "quality_reason_codes": reason_codes,
    }
