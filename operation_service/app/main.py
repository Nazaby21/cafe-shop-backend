from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import Base, engine
from app.dependencies.db import get_db

# Import models so SQLAlchemy registers them on Base.metadata before create_all().
from app.models.category import Category  # noqa: F401
from app.models.customization import CustomizationGroup, CustomizationOption  # noqa: F401
from app.models.product import Product  # noqa: F401
from app.models.order import Order, OrderItem  # noqa: F401
from app.models.payment import (  # noqa: F401
    IdempotencyRecord,
    Payment,
    PaymentAttempt,
    PaymentEvent,
    Refund,
    VerificationJob,
)
from app.models.stock_movement import StockMovement  # noqa: F401

from app.api.product_route import router as product_router
from app.api.order_route import router as order_router
from app.api.payment_route import payment_root_router, router as payment_router
from app.api.category_route import router as category_router

from app.core.exception import ApplicationError
from app.core.exception_handler import application_error_handler

# NOTE: create_all() is convenient for local development; Alembic migrations
# are provided in operation_service/migrations/ for production PostgreSQL.
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Coffee Shop - Operation & Bakong KHQR Payment Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["health"])
def health_check(db: Session = Depends(get_db)):
    """Health check verifying PostgreSQL connectivity and service status."""
    try:
        db.execute(text("SELECT 1"))
        return {
            "status": "ok",
            "service": "operation_service",
            "database": "connected",
            "bakong_mode": getattr(settings, "BAKONG_MODE", "mock"),
        }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "service": "operation_service",
                "database": str(e),
            },
        )


app.include_router(category_router)
app.include_router(product_router)
app.include_router(order_router)
app.include_router(payment_router)
app.include_router(payment_root_router)

app.add_exception_handler(ApplicationError, application_error_handler)


@app.get("/")
async def root():
    return {"message": "Coffee Shop Operation Service is running"}
