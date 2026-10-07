import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import projects, runs, uploads

app = FastAPI(title="Migration Platform API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.getenv("FRONTEND_ORIGIN", "http://localhost:3000").split(",")],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)
app.include_router(projects.router, prefix="/projects", tags=["projects"])
app.include_router(uploads.router, tags=["uploads"])
app.include_router(runs.router, tags=["runs"])


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
