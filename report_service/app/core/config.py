from dotenv import load_dotenv
import os

load_dotenv()


class Settings:
    # report_service now owns its own database (report_service_db), same as
    # user_service and operation_service each own theirs. It never connects
    # directly to the other two services' databases.
    DB_HOST = os.getenv("DB_HOST")
    DB_PORT = os.getenv("DB_PORT")
    DB_NAME = os.getenv("DB_NAME")
    DB_USER = os.getenv("DB_USER")
    DB_PASSWORD = os.getenv("DB_PASSWORD")

    # Base URLs used only by the sync job to pull data over HTTP from the
    # other two services - this is the only inter-service communication in
    # the whole system, and it is one-directional (report_service -> others).
    USER_SERVICE_BASE_URL = os.getenv("USER_SERVICE_BASE_URL", "http://127.0.0.1:8001")
    OPERATION_SERVICE_BASE_URL = os.getenv("OPERATION_SERVICE_BASE_URL", "http://127.0.0.1:8002")

    # Must match user_service's JWT_SECRET_KEY / JWT_ALGORITHM exactly:
    # - used to verify tokens presented by end users hitting /report/* endpoints
    # - also used by report_service itself to mint a short-lived internal
    #   "service account" token (role=admin) when calling user_service /
    #   operation_service during a sync
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-me-in-production")
    JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
    SERVICE_TOKEN_EXPIRE_MINUTES = int(os.getenv("SERVICE_TOKEN_EXPIRE_MINUTES", "5"))

    CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]

    SYNC_ON_STARTUP = os.getenv("SYNC_ON_STARTUP", "true").lower() == "true"
    SYNC_PAGE_SIZE = int(os.getenv("SYNC_PAGE_SIZE", "100"))


settings = Settings()
