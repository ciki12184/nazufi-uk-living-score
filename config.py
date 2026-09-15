import os

APP_ENV = os.getenv("APP_ENV", "development")
DATABASE_PATH = os.getenv("DATABASE_PATH", "./nazufi_living_score.db")
ALLOWED_ORIGINS = [
    x.strip() for x in os.getenv(
        "ALLOWED_ORIGINS",
        "https://www.nazufienterprise.com,https://nazufienterprise.com"
    ).split(",") if x.strip()
]
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:8000")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
