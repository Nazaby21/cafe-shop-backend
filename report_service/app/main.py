import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import Base, SessionLocal, engine

# Import models so SQLAlchemy registers them on Base.metadata before create_all().
from app.models.snapshot import OrderItemSnapshot, OrderSnapshot, ProductSnapshot, UserSnapshot

from app.api.report_route import router as report_router

from app.core.exception import ApplicationError
from app.core.exception_handler import application_error_handler
from app.services.sync_service import SyncService

logger = logging.getLogger("report_service")

# report_service now owns report_service_db outright (its snapshot tables),
# so - unlike the previous design that read other services' databases
# directly - create_all() here is exactly as safe as it is in user_service /
# operation_service.
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Coffee Shop - Report Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(report_router)

app.add_exception_handler(ApplicationError, application_error_handler)


@app.on_event("startup")
def _sync_on_startup():
    """
    Best-effort initial sync so reports aren't empty right after boot. This
    silently no-ops (with a log line) if user_service/operation_service
    aren't reachable yet - use POST /report/sync to trigger it manually once
    they're up, or wire this to a periodic job for production use.
    """
    if not settings.SYNC_ON_STARTUP:
        return
    db = SessionLocal()
    try:
        result = SyncService().sync_all(db)
        logger.info("Startup sync completed: %s", result)
    except Exception as exc:  # noqa: BLE001 - startup sync must never crash the app
        logger.warning("Startup sync skipped (upstream services not reachable yet?): %s", exc)
    finally:
        db.close()


@app.get("/")
async def root():
    return {"message": "Coffee Shop Report Service is running"}
