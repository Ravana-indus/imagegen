import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.db import initialize_database
from app.routes.auth import router as auth_router
from app.routes.exports import router as exports_router
from app.routes.items import router as items_router
from app.routes.projects import router as projects_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    initialize_database()
    yield


app = FastAPI(title="Product Creative API", lifespan=lifespan)
app.include_router(auth_router)
app.include_router(projects_router)
app.include_router(items_router)
app.include_router(exports_router)


@app.exception_handler(Exception)
async def catch_unhandled(_request: Request, exc: Exception) -> JSONResponse:
    if isinstance(exc, SQLAlchemyError):
        logger.exception("Database error during request")
        detail = "Database connection failed"
    elif isinstance(exc, (ModuleNotFoundError, ImportError)):
        logger.exception("Missing dependency")
        detail = "Server is missing a required package — check the API logs"
    else:
        logger.exception("Unhandled error during request")
        detail = str(exc)
    return JSONResponse(status_code=500, content={"detail": detail})


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


DEV_STORAGE_ROOT = Path(__file__).resolve().parents[2] / "dev-storage"


@app.get("/storage/{key:path}")
def serve_dev_asset(key: str) -> FileResponse:
    path = DEV_STORAGE_ROOT / key
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Asset not found")
    return FileResponse(path)
