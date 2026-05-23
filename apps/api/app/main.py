from fastapi import FastAPI

from app.routes.auth import router as auth_router
from app.routes.exports import router as exports_router
from app.routes.items import router as items_router
from app.routes.projects import router as projects_router

app = FastAPI(title="Product Creative API")
app.include_router(auth_router)
app.include_router(projects_router)
app.include_router(items_router)
app.include_router(exports_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
