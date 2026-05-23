from fastapi import FastAPI

from app.routes.auth import router as auth_router

app = FastAPI(title="Product Creative API")
app.include_router(auth_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
