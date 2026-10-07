"""Who is calling, and may they touch this project?

Real authentication (Clerk/Auth0) isn't wired up yet. Until it is, routes that
handle agency data only work when APP_ENV=development, and refuse everything
otherwise, so a deployed copy can't accidentally run with no login.
"""
import os
import re
from dataclasses import dataclass

from fastapi import HTTPException, Path, status

PROJECT_ID_RE = re.compile(r"[A-Za-z0-9_-]{1,64}")


@dataclass(frozen=True)
class Caller:
    user_id: str
    organisation_id: str


def require_project_access(project_id: str = Path(...)) -> Caller:
    if not PROJECT_ID_RE.fullmatch(project_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    if os.getenv("APP_ENV") != "development":
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "Authentication is not configured")
    # TODO(auth): verify the session token, then check the project belongs to the caller's organisation.
    return Caller(user_id="dev-user", organisation_id="dev-org")
