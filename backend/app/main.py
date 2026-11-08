import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import dq, local_files, projects, runs, uploads, layers, versions

app = FastAPI(title="Migryr API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.getenv("FRONTEND_ORIGIN", "http://localhost:3000").split(",")],
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)
app.include_router(projects.router, prefix="/projects", tags=["projects"])
app.include_router(uploads.router, tags=["uploads"])
app.include_router(runs.router, tags=["runs"])
app.include_router(dq.router, prefix="/dq", tags=["data quality"])
app.include_router(local_files.router, tags=["local uploads"])
app.include_router(layers.router, prefix="/layers", tags=["middle tier and target"])
app.include_router(versions.router, prefix="/versions", tags=["versions (Dolt)"])


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
