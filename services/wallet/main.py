from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from ..shared.logging import configure_logging, logger
from ..shared.settings import settings
from .router import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging("wallet-service", settings.environment)
    logger.info("wallet-service starting", env=settings.environment)
    yield
    logger.info("wallet-service shutting down")


app = FastAPI(
    title="FlightAI Wallet Service",
    version="1.0.0",
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
    lifespan=lifespan,
)

app.include_router(router, prefix="/v1")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "wallet"}
