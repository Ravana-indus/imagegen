from fastapi import FastAPI

app = FastAPI(title="Product Creative API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
