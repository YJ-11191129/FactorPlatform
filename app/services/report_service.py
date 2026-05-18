from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from uuid import uuid4

import pandas as pd
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.db.session import db_session
from app.models.analysis_result import AnalysisResult
from app.models.report_artifact import ReportArtifact
from app.services.native_qlib_research_service import get_factor_mining_run, get_portfolio


def _template_env() -> Environment:
    root = Path(__file__).resolve().parents[1]
    loader = FileSystemLoader(str(root / "reports" / "templates"))
    return Environment(loader=loader, autoescape=select_autoescape(["html", "xml"]))


def _fmt(x: Any) -> str:
    try:
        if x is None:
            return "-"
        v = float(x)
        if v != v:
            return "-"
        return f"{v:.4f}"
    except Exception:
        return "-"


def _pct(x: Any) -> str:
    try:
        if x is None:
            return "-"
        v = float(x)
        if v != v:
            return "-"
        return f"{v * 100:.1f}%"
    except Exception:
        return "-"


def generate_single_factor_report(analysis_id: str, enable_pdf: bool = False) -> dict[str, Any]:
    with db_session() as db:
        a = db.get(AnalysisResult, analysis_id)
    if a is None:
        raise ValueError("analysis not found")

    artifact_dir = Path(a.artifact_path)
    if not artifact_dir.exists():
        raise FileNotFoundError(f"analysis artifact not found: {artifact_dir}")

    ic_path = artifact_dir / "ic_series.parquet"
    grp_path = artifact_dir / "group_returns.parquet"
    ic_tail = []
    grp_tail = []
    if ic_path.exists():
        ic_df = pd.read_parquet(ic_path).tail(30)
        ic_tail = ic_df.to_dict(orient="records")
    if grp_path.exists():
        grp_df = pd.read_parquet(grp_path).tail(50)
        grp_tail = grp_df.to_dict(orient="records")

    env = _template_env()
    tpl = env.get_template("single_factor_report.html")
    html = tpl.render(summary=a.summary, ic_tail=ic_tail, grp_tail=grp_tail, fmt=_fmt, pct=_pct)

    report_id = uuid4().hex
    html_path = artifact_dir / "report.html"
    html_path.write_text(html, encoding="utf-8")

    pdf_path: Path | None = None
    meta: dict[str, Any] = {}

    if enable_pdf or os.getenv("FACTOR_PLATFORM_ENABLE_PDF", "0") in {"1", "true", "True", "YES", "yes"}:
        try:
            from weasyprint import HTML

            pdf_path = artifact_dir / "report.pdf"
            HTML(string=html, base_url=str(artifact_dir)).write_pdf(str(pdf_path))
        except Exception as e:
            meta["pdf_error"] = str(e)
            pdf_path = None

    try:
        with db_session() as db:
            db.add(
                ReportArtifact(
                    report_id=report_id,
                    report_type="single_factor",
                    analysis_id=analysis_id,
                    status="SUCCESS",
                    meta=meta,
                    html_path=str(html_path),
                    pdf_path=(str(pdf_path) if pdf_path else None),
                )
            )
    except Exception:
        pass

    result = {
        "report_id": report_id,
        "analysis_id": analysis_id,
        "html_path": str(html_path),
        "pdf_path": (str(pdf_path) if pdf_path else None),
        "meta": meta,
    }
    try:
        from app.services.research_ops_registry import register_report_artifact

        register_report_artifact(result, report_type="single_factor")
    except Exception:
        pass
    return result


def _write_optional_pdf(html: str, artifact_dir: Path, enable_pdf: bool, meta: dict[str, Any]) -> Path | None:
    if enable_pdf or os.getenv("FACTOR_PLATFORM_ENABLE_PDF", "0") in {"1", "true", "True", "YES", "yes"}:
        try:
            from weasyprint import HTML

            pdf_path = artifact_dir / "report.pdf"
            HTML(string=html, base_url=str(artifact_dir)).write_pdf(str(pdf_path))
            return pdf_path
        except Exception as e:
            meta["pdf_error"] = str(e)
    return None


def _persist_report_record(
    report_id: str,
    report_type: str,
    analysis_id: str,
    meta: dict[str, Any],
    html_path: Path,
    pdf_path: Path | None,
) -> None:
    try:
        with db_session() as db:
            db.add(
                ReportArtifact(
                    report_id=report_id,
                    report_type=report_type,
                    analysis_id=analysis_id,
                    status="SUCCESS",
                    meta=meta,
                    html_path=str(html_path),
                    pdf_path=(str(pdf_path) if pdf_path else None),
                )
            )
    except Exception:
        pass


def generate_qlib_factor_mining_report(run_id: str, enable_pdf: bool = False) -> dict[str, Any]:
    run = get_factor_mining_run(run_id)
    summary = run["summary"]
    artifact_dir = Path(summary["artifact_path"])
    if not artifact_dir.exists():
        raise FileNotFoundError(f"factor mining artifact not found: {artifact_dir}")

    env = _template_env()
    tpl = env.get_template("qlib_factor_mining_report.html")
    html = tpl.render(
        summary=summary,
        ranking=run["factor_ranking"][:100],
        ic_tail=run["ic_series"][-200:],
        group_returns=run["group_returns"][-200:],
        fmt=_fmt,
        pct=_pct,
    )

    report_id = uuid4().hex
    html_path = artifact_dir / "report.html"
    html_path.write_text(html, encoding="utf-8")
    meta = {"run_id": run_id, "report_type": "qlib_factor_mining", "data_source": "qlib_factor_mining_artifacts"}
    pdf_path = _write_optional_pdf(html, artifact_dir, enable_pdf=enable_pdf, meta=meta)
    _persist_report_record(report_id, "qlib_factor_mining", run_id, meta, html_path, pdf_path)
    result = {
        "report_id": report_id,
        "analysis_id": run_id,
        "html_path": str(html_path),
        "pdf_path": (str(pdf_path) if pdf_path else None),
        "meta": meta,
    }
    try:
        from app.services.research_ops_registry import register_report_artifact

        register_report_artifact(result, report_type="qlib_factor_mining")
    except Exception:
        pass
    return result


def generate_qlib_portfolio_backtest_report(
    portfolio_id: str,
    backtest_id: str | None = None,
    enable_pdf: bool = False,
) -> dict[str, Any]:
    portfolio = get_portfolio(portfolio_id)
    artifact_dir = Path(str(portfolio["signal_artifact_path"])).parent
    if not artifact_dir.exists():
        raise FileNotFoundError(f"portfolio artifact not found: {artifact_dir}")

    backtest: dict[str, Any] | None = None
    if backtest_id:
        from app.services.backtest_service import _select_backtest_root

        summary_path = _select_backtest_root() / backtest_id / "summary.json"
        if not summary_path.exists():
            raise FileNotFoundError(f"backtest summary not found: {backtest_id}")
        import json

        backtest = json.loads(summary_path.read_text(encoding="utf-8"))

    env = _template_env()
    tpl = env.get_template("qlib_portfolio_backtest_report.html")
    html = tpl.render(portfolio=portfolio, backtest=backtest, fmt=_fmt, pct=_pct)

    report_id = uuid4().hex
    html_path = artifact_dir / "report.html"
    html_path.write_text(html, encoding="utf-8")
    meta = {
        "portfolio_id": portfolio_id,
        "backtest_id": backtest_id,
        "report_type": "qlib_portfolio_backtest",
        "data_source": "qlib_portfolio_backtest_artifacts",
    }
    pdf_path = _write_optional_pdf(html, artifact_dir, enable_pdf=enable_pdf, meta=meta)
    _persist_report_record(report_id, "qlib_portfolio_backtest", portfolio_id, meta, html_path, pdf_path)
    result = {
        "report_id": report_id,
        "analysis_id": portfolio_id,
        "html_path": str(html_path),
        "pdf_path": (str(pdf_path) if pdf_path else None),
        "meta": meta,
    }
    try:
        from app.services.research_ops_registry import register_report_artifact

        register_report_artifact(result, report_type="qlib_portfolio_backtest")
    except Exception:
        pass
    return result
