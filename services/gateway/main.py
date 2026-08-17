"""
FlightAI API Gateway — single public entry point for all services.
Routes /v1/* requests to the correct backend Cloud Run service.
"""
import os
import httpx
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="FlightAI API Gateway")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

USER_URL      = os.environ["USER_SERVICE_URL"].rstrip("/")
WALLET_URL    = os.environ["WALLET_SERVICE_URL"].rstrip("/")
BOOKING_URL   = os.environ["BOOKING_SERVICE_URL"].rstrip("/")
ORCHESTRATOR_URL = os.environ["ORCHESTRATOR_URL"].rstrip("/")

# Longest-prefix match — order matters
ROUTES = [
    ("/v1/admin/bookings", BOOKING_URL),
    ("/v1/admin/users",    USER_URL),
    ("/v1/admin",          USER_URL),
    ("/v1/auth",           USER_URL),
    ("/v1/me",             USER_URL),
    ("/v1/users",          USER_URL),
    ("/v1/wallet",         WALLET_URL),
    ("/v1/routes",         BOOKING_URL),
    ("/v1/bookings",       BOOKING_URL),
    ("/v1/flights",        BOOKING_URL),
    ("/v1/agent",          ORCHESTRATOR_URL),
]

HOP_BY_HOP = {
    "connection", "keep-alive", "transfer-encoding", "te",
    "trailers", "upgrade", "proxy-authorization", "proxy-authenticate",
    "host", "content-encoding",
}


def _upstream(path: str) -> str:
    for prefix, url in ROUTES:
        if path.startswith(prefix):
            return url
    return USER_URL


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
async def proxy(request: Request, path: str):
    full_path = "/" + path
    if request.url.query:
        full_path += "?" + request.url.query

    upstream = _upstream("/" + path)
    target_url = upstream + full_path

    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in HOP_BY_HOP
    }

    body = await request.body()

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.request(
            method=request.method,
            url=target_url,
            headers=headers,
            content=body,
        )

    resp_headers = {
        k: v for k, v in resp.headers.items()
        if k.lower() not in HOP_BY_HOP
    }

    return Response(
        content=resp.content,
        status_code=resp.status_code,
        headers=resp_headers,
        media_type=resp.headers.get("content-type"),
    )


@app.get("/health")
async def health():
    return {"status": "ok", "service": "gateway"}
