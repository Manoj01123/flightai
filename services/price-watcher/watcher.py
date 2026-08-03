import uuid
from datetime import datetime, timezone, timedelta

import redis.asyncio as aioredis
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from ..shared.database import AsyncSessionLocal
from ..shared.logging import logger
from ..shared.settings import settings
from ..booking.models import Route, PriceSnapshot, RouteStatus
from .duffel_client import duffel_client


POLL_INTERVAL_MINUTES = 1
REDIS_DEDUP_TTL_SECONDS = 50  # slightly less than poll interval


class PriceWatcherScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self._redis: aioredis.Redis | None = None

    async def start(self):
        try:
            self._redis = aioredis.from_url(settings.redis_url, decode_responses=True)
            await self._redis.ping()
        except Exception:
            logger.warning("redis unavailable, dedup disabled")
            self._redis = None
        self.scheduler.add_job(
            self._poll_all_active_routes,
            "interval",
            minutes=POLL_INTERVAL_MINUTES,
            id="price_poll",
            replace_existing=True,
        )
        self.scheduler.start()
        logger.info("price watcher started", interval_minutes=POLL_INTERVAL_MINUTES)

    async def stop(self):
        self.scheduler.shutdown(wait=False)
        if self._redis:
            try:
                await self._redis.aclose()
            except Exception:
                pass
        await duffel_client.close()

    async def _poll_all_active_routes(self):
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Route).where(Route.status == RouteStatus.ACTIVE)
            )
            routes = result.scalars().all()
            logger.info("polling active routes", count=len(routes))
            for route in routes:
                await self._poll_route(route)

    async def _poll_route(self, route: Route):
        cache_key = f"price_poll:{route.origin}:{route.destination}:{route.date_from}"
        if self._redis and await self._redis.exists(cache_key):
            logger.debug("cache hit, skipping poll", route_id=route.id, cache_key=cache_key)
            return

        try:
            offers = await duffel_client.search_flights(
                origin=route.origin,
                destination=route.destination,
                departure_date=route.date_from,
                adults=route.adults,
                cabin_class=route.cabin_class,
            )
            result = duffel_client.extract_best_price(offers)
            if result is None:
                logger.warning("no offers returned", route_id=route.id)
                return

            price, airline, flight_number = result

            async with AsyncSessionLocal() as db:
                snapshot = PriceSnapshot(
                    id=str(uuid.uuid4()),
                    route_id=route.id,
                    price=price,
                    airline=airline,
                    flight_number=flight_number,
                    fetched_at=datetime.now(timezone.utc),
                )
                db.add(snapshot)
                await db.commit()

            if self._redis:
                await self._redis.setex(cache_key, REDIS_DEDUP_TTL_SECONDS, "1")

            logger.info(
                "price snapshot saved",
                route_id=route.id,
                price=str(price),
                airline=airline,
            )

            await self._publish_price_event(route, price, airline, flight_number)

        except Exception as e:
            logger.error("poll failed", route_id=route.id, error=str(e))

    async def _publish_price_event(self, route: Route, price, airline: str, flight_number: str):
        from google.cloud import pubsub_v1
        import json

        publisher = pubsub_v1.PublisherClient()
        topic_path = publisher.topic_path(
            settings.gcp_project_id, settings.pubsub_topic_price_updated
        )
        message = {
            "route_id": route.id,
            "user_id": route.user_id,
            "origin": route.origin,
            "destination": route.destination,
            "price": str(price),
            "target_price": str(route.target_price),
            "airline": airline,
            "flight_number": flight_number,
            "booking_mode": route.booking_mode,
            "departure_date": route.date_from.isoformat() if route.date_from else None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        publisher.publish(topic_path, data=json.dumps(message).encode())


watcher = PriceWatcherScheduler()
