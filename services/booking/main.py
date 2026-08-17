from contextlib import asynccontextmanager

from fastapi import FastAPI

from ..shared.logging import configure_logging, logger
from ..shared.settings import settings
from .router import routes_router, bookings_router, flights_router, admin_bookings_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging("booking-service", settings.environment)
    logger.info("booking-service starting", env=settings.environment)
    yield
    logger.info("booking-service shutting down")


app = FastAPI(
    title="FlightAI Booking Service",
    version="1.0.0",
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
    lifespan=lifespan,
)

app.include_router(routes_router, prefix="/v1")
app.include_router(bookings_router, prefix="/v1")
app.include_router(flights_router, prefix="/v1")
app.include_router(admin_bookings_router, prefix="/v1")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "booking"}
