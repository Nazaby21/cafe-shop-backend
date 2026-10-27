from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import Base, engine

from app.models.user import User
from app.api.user_route import router as user_router
from app.core.exception import ApplicationError
from app.core.exception_handler import application_error_handler


# NOTE: create_all() is convenient for local development but should be
# replaced by Alembic migrations before this ever touches a shared/prod DB.
Base.metadata.create_all(bind=engine)


app = FastAPI(
    title="Coffee Shop - Auth Service",
    description="""
    ## Coffee Shop Authentication Service

    This service provides authentication and user management APIs.

    ### Features

    - User registration
    - User login
    - JWT authentication
    - Get current user
    - User management
    - Role management
    - Password management
    - User deletion

    ### Authentication

    Protected endpoints require a JWT access token.
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(user_router)

app.add_exception_handler(
    ApplicationError,
    application_error_handler,
)