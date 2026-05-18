import logging

from fastapi import FastAPI

from app.api.routers.analysis import router as analysis_router
from app.api.routers.audit import router as audit_router
from app.api.routers.backtests import router as backtests_router
from app.api.routers.data_maintenance import router as data_maintenance_router
from app.api.routers.factors import router as factors_router
from app.api.routers.macro import router as macro_router
from app.api.routers.news import router as news_router
from app.api.routers.openbb import router as openbb_router
from app.api.routers.qlib_research import router as qlib_research_router
from app.api.routers.reports import router as reports_router
from app.api.routers.research_quality import router as research_quality_router
from app.api.routers.research_ops import router as research_ops_router
from app.api.routers.root import router as root_router
from app.api.routers.runs import router as runs_router
from app.api.routers.signal_center import router as signal_center_router
from app.api.routers.tasks import router as tasks_router
from app.api.middleware.audit import audit_middleware
from app.core.settings import get_settings, validate_runtime_settings
from app.db.session import db_session, init_db
from app.services.factor_metadata_service import sync_code_factor_metadata


def create_app() -> FastAPI:
    app = FastAPI(title="FactorPlatform API")
    app.middleware("http")(audit_middleware)
    app.include_router(root_router)
    app.include_router(factors_router)
    app.include_router(runs_router)
    app.include_router(signal_center_router)
    app.include_router(macro_router)
    app.include_router(news_router)
    app.include_router(openbb_router)
    app.include_router(tasks_router)
    app.include_router(analysis_router)
    app.include_router(qlib_research_router)
    app.include_router(reports_router)
    app.include_router(research_quality_router)
    app.include_router(research_ops_router)
    app.include_router(audit_router)
    app.include_router(backtests_router)
    app.include_router(data_maintenance_router)

    @app.on_event("startup")
    def _startup() -> None:
        settings = get_settings()
        validate_runtime_settings(settings)
        try:
            if settings.require_db:
                init_db()
                with db_session() as db:
                    sync_code_factor_metadata(db)
        except Exception:
            logging.getLogger("factor_platform.startup").exception("startup db init failed")
            if settings.require_db:
                raise

    return app


app = create_app()
