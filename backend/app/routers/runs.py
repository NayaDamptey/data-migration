from fastapi import APIRouter

from app.models import FieldReview, Run

router = APIRouter()


@router.post("/projects/{project_id}/runs", response_model=Run)
def start_run(project_id: str):
    """Creates a new version and queues ingest → inspect."""
    raise NotImplementedError


@router.get("/runs/{run_id}", response_model=Run)
def get_run(run_id: str):
    raise NotImplementedError


@router.get("/runs/{run_id}/inspection")
def get_inspection(run_id: str):
    """Inspect button: profile summary, tables, warnings."""
    raise NotImplementedError


@router.post("/runs/{run_id}/canonical")
def run_canonical(run_id: str):
    """Run canonical layer: AI mapping + canonical models."""
    raise NotImplementedError


@router.get("/runs/{run_id}/canonical/{entity}")
def get_canonical_fields(run_id: str, entity: str):
    """Screen 3: fields, source column, sample, status."""
    raise NotImplementedError


@router.post("/runs/{run_id}/reviews")
def submit_reviews(run_id: str, reviews: list[FieldReview]):
    raise NotImplementedError


@router.post("/runs/{run_id}/target")
def run_target(run_id: str):
    """Run target: build + validate target tables."""
    raise NotImplementedError


@router.get("/runs/{run_id}/target/{entity}")
def get_target_preview(run_id: str, entity: str):
    """Screen 4: preview rows, ready/warning/rejected counts, issues."""
    raise NotImplementedError


@router.get("/runs/{run_id}/outputs")
def list_outputs(run_id: str):
    """Get data: files with pre-signed download URLs (every download is logged)."""
    raise NotImplementedError
