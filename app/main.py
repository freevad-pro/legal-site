import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from datetime import timedelta

from fastapi import FastAPI

from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.api.scan import router as scan_router
from app.auth import purge_expired_sessions
from app.config import settings
from app.corpus.loader import load_corpus
from app.db import init_db
from app.logging_config import setup_logging
from app.scan_state import ScanRegistry

setup_logging(settings.log_level)
logger = logging.getLogger(__name__)


async def _purge_loop(registry: ScanRegistry) -> None:
    """Раз в минуту чистит просроченные терминальные state'ы."""

    while True:
        try:
            await asyncio.sleep(60)
            removed = registry.purge_expired()
            if removed:
                logger.info("purged %d expired scan state(s)", removed)
        except asyncio.CancelledError:
            return
        except Exception:  # noqa: BLE001 - не даём фоновой таске убить себя
            logger.exception("purge loop iteration failed")


async def _purge_sessions_loop() -> None:
    """Раз в час чистит просроченные cookie-сессии.

    Дополняет ленивую очистку в `login` для случая, когда пользователь
    долго не входит, а записи в `sessions` всё накапливаются.
    """

    while True:
        try:
            await asyncio.sleep(3600)
            await purge_expired_sessions()
        except asyncio.CancelledError:
            return
        except Exception:  # noqa: BLE001 - не даём фоновой таске убить себя
            logger.exception("session purge iteration failed")


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_db(settings.database_path)
    app.state.corpus = load_corpus(settings.corpus_path)
    app.state.scan_registry = ScanRegistry(
        ttl=timedelta(seconds=settings.scan_state_ttl_seconds)
    )
    app.state.scan_semaphore = asyncio.Semaphore(1)
    # Сильные ссылки на фоновые таски сканов — без этого Python GC может
    # прибрать асинхронную таску до завершения. Воркер сам удаляет себя
    # отсюда через `add_done_callback`.
    app.state.background_tasks = set()
    purge_task = asyncio.create_task(_purge_loop(app.state.scan_registry))
    sessions_purge_task = asyncio.create_task(_purge_sessions_loop())
    logger.info("Legal_site started; corpus loaded, DB ready")
    try:
        yield
    finally:
        for bg_task in (purge_task, sessions_purge_task):
            bg_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await bg_task
        # Дожидаемся, чтобы пользовательские сканы не оборвались на shutdown.
        for task in list(app.state.background_tasks):
            with contextlib.suppress(Exception):
                await task


app = FastAPI(title="Legal_site", version="0.1.0", lifespan=lifespan)
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(scan_router)
