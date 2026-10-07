from fastapi import APIRouter

from app.models import ChangeRequest, Project, ProjectCreate

router = APIRouter()


@router.post("", response_model=Project)
def create_project(body: ProjectCreate):
    """Screen 2: save source/target choices."""
    raise NotImplementedError


@router.get("/{project_id}", response_model=Project)
def get_project(project_id: str):
    raise NotImplementedError


@router.get("/{project_id}/runs")
def list_runs(project_id: str):
    """Runs & versions panel."""
    raise NotImplementedError


@router.post("/{project_id}/change-requests")
def create_change_request(project_id: str, body: ChangeRequest):
    """Plain-English change request → AI proposes a new mapping spec version."""
    raise NotImplementedError
