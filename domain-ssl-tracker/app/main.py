from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.logging_config import setup_logging
from app.database import init_db
from app.scheduler import start_scheduler, stop_scheduler
from app.routes import domains as domains_router
from app.routes import dashboard as dashboard_router

setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_db()
    start_scheduler()
    yield
    # Shutdown
    stop_scheduler()


app = FastAPI(
    title="Domain & SSL Expiry Tracker",
    description="Track SSL and domain expiry dates with automated email alerts.",
    version="1.0.0",
    lifespan=lifespan,
)

# Static files (CSS, JS)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Dashboard (HTML routes)
app.include_router(dashboard_router.router, tags=["Dashboard"])

# REST API routes
app.include_router(domains_router.router, prefix="/api", tags=["API"])
