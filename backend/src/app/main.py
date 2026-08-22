from fastapi import FastAPI

app = FastAPI(title="Intelligent Process Observer")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
