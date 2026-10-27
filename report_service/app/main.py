from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import Base, engine

# Import models so SQLAlchemy registers them on Base.metadata before create_all().
from app.models.snapshot import OrderItemSnapshot, OrderSnapshot, ProductSnapshot, UserSnapshot

from app.api.report_route import router as report_router

from app.core.exception import ApplicationError
from app.core.exception_handler import application_error_handler

# Ensure snapshot tables exist
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


@app.get("/")
async def root():
    return {"message": "Coffee Shop Report Service is running"}
