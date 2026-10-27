from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import Base, engine

# Import models so SQLAlchemy registers them on Base.metadata before create_all().
from app.models.category import Category
from app.models.customization import CustomizationGroup, CustomizationOption
from app.models.product import Product
from app.models.order import Order, OrderItem
from app.models.payment import Payment
from app.models.stock_movement import StockMovement

from app.api.product_route import router as product_router
from app.api.order_route import router as order_router
from app.api.payment_route import router as payment_router
from app.api.category_route import router as category_router

from app.core.exception import ApplicationError
from app.core.exception_handler import application_error_handler

# NOTE: create_all() is convenient for local development but should be
# replaced by Alembic migrations before this ever touches a shared/prod DB.
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Coffee Shop - Operation Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(category_router)
app.include_router(product_router)
app.include_router(order_router)
app.include_router(payment_router)

app.add_exception_handler(ApplicationError, application_error_handler)


@app.get("/")
async def root():
    return {"message": "Coffee Shop Operation Service is running"}
