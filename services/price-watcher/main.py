from contextlib import asynccontextmanager

from fastapi import FastAPI

from ..shared.logging import configure_logging, logger
from ..shared.settings import settings
from .watcher import watcher


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging("price-watcher", settings.environment)
    logger.info("price-watcher starting")
    await watcher.start()
    yield
    await watcher.stop()
    logger.info("price-watcher stopped")


app = FastAPI(
    title="FlightAI Price Watcher",
    version="1.0.0",
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "price-watcher", "scheduler_running": watcher.scheduler.running}


@app.post("/poll/trigger", include_in_schema=False)
async def manual_trigger():
    """Admin-only endpoint for triggering a manual poll cycle."""
    await watcher._poll_all_active_routes()
    return {"status": "triggered"}
