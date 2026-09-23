import time
import logging
from fastapi import FastAPI, Request, status, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError

from app.config import settings
from app.database.connection import check_db_connection
from app.api.v1 import (
    auth, clients, agents, policies, jobs, backups, restore, storage, retention, activity, dashboard
)

# Structured application logging
logging.basicConfig(
    level=logging.INFO if settings.DEBUG else logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("retrovault.control_plane")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS if isinstance(settings.CORS_ORIGINS, list) else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request logging middleware (excluding credentials/secrets)
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    logger.info(
        f"{request.method} {request.url.path} completed with status {response.status_code} in {duration:.4f}s"
    )
    return response

# Standard JSON error response handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "code": f"HTTP_{exc.status_code}",
                "message": exc.detail
            }
        }
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "details": exc.errors()
            }
        }
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception on {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An internal server error occurred"
            }
        }
    )

# Health Check endpoint
@app.get("/health", tags=["Health"])
def health_check():
    db_connected = check_db_connection()
    return {
        "status": "ok" if db_connected else "degraded",
        "database": "connected" if db_connected else "disconnected",
        "version": "1.0.0"
    }

# Register API v1 routers
app.include_router(auth.router, prefix=settings.API_V1_STR)
app.include_router(clients.router, prefix=settings.API_V1_STR)
app.include_router(agents.router, prefix=settings.API_V1_STR)
app.include_router(policies.router, prefix=settings.API_V1_STR)
app.include_router(jobs.router, prefix=settings.API_V1_STR)
app.include_router(backups.router, prefix=settings.API_V1_STR)
app.include_router(restore.router, prefix=settings.API_V1_STR)
app.include_router(storage.router, prefix=settings.API_V1_STR)
app.include_router(retention.router, prefix=settings.API_V1_STR)
app.include_router(activity.router, prefix=settings.API_V1_STR)
app.include_router(dashboard.router, prefix=settings.API_V1_STR)


@app.on_event("startup")
def startup_reconcile():
    """Crash recovery: reconcile any stranded DELETING objects upon server start."""
    try:
        from app.database.session import SessionLocal
        from app.services.gc.garbage_collector import GarbageCollector
        with SessionLocal() as db:
            gc = GarbageCollector(db)
            reconciled = gc.reconcile_startup_state()
            if reconciled > 0:
                logger.info(f"Reconciled {reconciled} stranded storage objects on startup")
    except Exception as e:
        logger.warning(f"Startup GC reconciliation notice: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
