import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from database.database import Base, DB_TYPE, engine
from app.config import settings

# Import models so SQLAlchemy can register their metadata.
from app.monitoring.model import MonitoringHistory
from app.speed_monitoring.model import DeviceBandwidthHistory, DeviceSpeedTestJob
from app.alerts.model import Alert

# Routers
from app.devices.router import router as devices_router
from app.discovery.router import router as discovery_router
from app.monitoring.router import router as monitoring_router
from app.speed_monitoring.router import router as speed_monitoring_router
from app.auth.router import router as auth_router
from app.settings.router import router as set_router
from app.topology.router import router as topology_router
from app.dashboard.router import router as dashboard_router
from app.alerts.router import router as alerts_router
from app.reports.router import router as reports_router
from app.metrics.router import router as metrics_router
from app.monitoring.scheduler import monitor_devices
from app.agent.router import router as agent_router

# ==================================================
# PATH CONFIGURATION
# ==================================================

BASE_DIR = Path(__file__).resolve().parent

FRONTEND_DIST = Path(
    os.getenv(
        "NMVS_FRONTEND_DIST",
        str(BASE_DIR.parent / "nmvs_frontend" / "dist"),
    )
).resolve()

FRONTEND_INDEX = FRONTEND_DIST / "index.html"


# ==================================================
# CORS CONFIGURATION
# ==================================================

DEFAULT_CORS_ORIGINS = [
    "https://nmvs-development.onrender.com",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
]


def get_allowed_origins() -> list[str]:
    configured_origins = os.getenv("CORS_ALLOWED_ORIGINS")

    if not configured_origins:
        return DEFAULT_CORS_ORIGINS

    origins = [
        origin.strip().rstrip("/")
        for origin in configured_origins.split(",")
        if origin.strip()
    ]

    return origins or DEFAULT_CORS_ORIGINS


# ==================================================
# APPLICATION LIFESPAN
# ==================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    from database.database import init_db

    # Run database migrations where configured.
    alembic_ini_path = BASE_DIR / "alembic.ini"

    if alembic_ini_path.is_file() and DB_TYPE != "sqlite":
        from alembic import command
        from alembic.config import Config

        alembic_config = Config(str(alembic_ini_path))
        command.upgrade(alembic_config, "head")

    init_db()

    # Start the monitoring scheduler.
    monitoring_task = asyncio.create_task(
        monitor_devices(settings.DEVICE_MONITOR_INTERVAL)
    )

    try:
        yield
    finally:
        monitoring_task.cancel()

        try:
            await monitoring_task
        except asyncio.CancelledError:
            pass


# ==================================================
# CREATE FASTAPI APPLICATION ONCE
# ==================================================

app = FastAPI(
    title="Network Monitoring and Visualization System",
    version="1.0.0",
    lifespan=lifespan,
)


# ==================================================
# CORS MIDDLEWARE
# ==================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=True,
    allow_methods=[
        "GET",
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
        "OPTIONS",
    ],
    allow_headers=["*"],
    max_age=600,
)


# ==================================================
# REGISTER API ROUTERS
# ==================================================

app.include_router(auth_router)
app.include_router(set_router)
app.include_router(devices_router)
app.include_router(discovery_router)
app.include_router(monitoring_router)
app.include_router(speed_monitoring_router)
app.include_router(topology_router)
app.include_router(dashboard_router)
app.include_router(alerts_router)
app.include_router(reports_router)
app.include_router(metrics_router)
app.include_router(agent_router)

# ==================================================
# ROOT ENDPOINT
# ==================================================

@app.get("/")
def home():
    if FRONTEND_INDEX.is_file():
        return FileResponse(FRONTEND_INDEX)

    return {
        "message": "NMVS API is running",
        "service": "Network Monitoring and Visualization System",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }


# ==================================================
# HEALTH CHECK
# ==================================================

@app.get("/health")
def health():
    from database.database import get_db_stats

    db_stats = get_db_stats()

    healthy = all(
        count != "unavailable"
        for count in db_stats.get("tables", {}).values()
    )

    return JSONResponse(
        status_code=200 if healthy else 503,
        content={
            "status": "healthy" if healthy else "unhealthy",
            "service": "Network Monitoring and Visualization System API",
            "version": "1.0.0",
            "database": db_stats,
        },
    )


# ==================================================
# FRONTEND STATIC FILES / SPA FALLBACK
# ==================================================

@app.get("/{frontend_path:path}", include_in_schema=False)
def serve_frontend(frontend_path: str, request: Request):
    if not FRONTEND_INDEX.is_file():
        raise HTTPException(
            status_code=404,
            detail="Not Found",
        )

    requested_file = (FRONTEND_DIST / frontend_path).resolve()

    # Do not serve files outside the frontend directory.
    if (
        requested_file.is_relative_to(FRONTEND_DIST)
        and requested_file.is_file()
    ):
        return FileResponse(requested_file)

    # React SPA fallback.
    if "text/html" in request.headers.get("accept", ""):
        return FileResponse(FRONTEND_INDEX)

    raise HTTPException(
        status_code=404,
        detail="Not Found",
    )
