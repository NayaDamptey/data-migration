"""Request/response shapes. Database tables are listed in docs/architecture.md."""
from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class SourceFormat(str, Enum):
    csv = "csv"
    backup = "backup"
    json = "json"
    api = "api"


class TargetDialect(str, Enum):
    mysql = "mysql"
    postgres = "postgres"
    tsql = "tsql"


class OutputType(str, Enum):
    csv = "csv"
    sql_inserts = "sql_inserts"
    api = "api"


class RunStatus(str, Enum):
    uploaded = "uploaded"
    inspecting = "inspecting"
    inspected = "inspected"
    mapping = "mapping"
    needs_review = "needs_review"
    canonical_ready = "canonical_ready"
    target_ready = "target_ready"
    delivered = "delivered"
    superseded = "superseded"
    failed = "failed"


class ProjectCreate(BaseModel):
    name: str
    source_system: str
    source_format: SourceFormat
    target_system: str
    target_dialect: TargetDialect
    output_type: OutputType = OutputType.csv


class Project(ProjectCreate):
    id: str
    created_at: datetime


class Run(BaseModel):
    id: str
    project_id: str
    version: int
    status: RunStatus
    mapping_spec_version: int | None = None
    started_at: datetime


class FieldReview(BaseModel):
    entity: str
    field: str
    decision: str          # accept | change | reject
    new_source: str | None = None
    comment: str | None = None


class ChangeRequest(BaseModel):
    run_id: str
    text: str              # plain English from the agency
