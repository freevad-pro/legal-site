import logging

from fastapi import FastAPI

from app.api.health import router as health_router
from app.config import settings

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

app = FastAPI(title="Legal_site", version="0.1.0")
app.include_router(health_router)
