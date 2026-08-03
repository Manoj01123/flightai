from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from ..shared.logging import configure_logging, logger
from ..shared.settings import settings
from .router import router, me_router, users_router, admin_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging("user-service", settings.environment)
    logger.info("user-service starting", env=settings.environment)
    yield
    logger.info("user-service shutting down")


app = FastAPI(
    title="FlightAI User Service",
    version="1.0.0",
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
    lifespan=lifespan,
)

app.include_router(router, prefix="/v1")
app.include_router(me_router, prefix="/v1")
app.include_router(users_router, prefix="/v1")
app.include_router(admin_router, prefix="/v1")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "user"}


@app.exception_handler(Exception)
async def generic_handler(request: Request, exc: Exception):
    logger.error("unhandled exception", exc_info=exc, path=str(request.url))
    return JSONResponse(
        status_code=500,
        content={"type": "internal_error", "title": "Internal Server Error", "status": 500},
    )
