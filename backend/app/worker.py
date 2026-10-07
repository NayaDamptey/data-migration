"""Background jobs (Celery). Each task moves a run to its next status."""
import os

from celery import Celery

celery = Celery("migration", broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"))


@celery.task
def ingest(run_id: str): ...        # unzip / restore backup / read JSON / pull API → Parquet


@celery.task
def inspect(run_id: str): ...       # pipeline/profiling/profile_source.py


@celery.task
def propose_mapping(run_id: str): ...  # pipeline/mapping/propose_mapping.py


@celery.task
def build_canonical(run_id: str): ...  # generate + run SQLMesh canonical models


@celery.task
def build_target(run_id: str): ...     # SQLMesh target models + audits


@celery.task
def deliver(run_id: str): ...          # CSVs + data dictionary / SQL inserts / API push
