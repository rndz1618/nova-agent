import secrets
import hashlib
from pathlib import Path
from typing import Annotated
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .config import get_settings, Settings

security_scheme = HTTPBearer(auto_error=False)


def verify_api_key(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security_scheme)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> str:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header. Use: Bearer <NOVA_API_KEY>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Constant-time comparison to prevent timing attacks
    provided = credentials.credentials.encode()
    expected = settings.nova_api_key.encode()

    if not secrets.compare_digest(
        hashlib.sha256(provided).digest(),
        hashlib.sha256(expected).digest(),
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials


def safe_resolve_path(user_path: str, settings: Settings) -> Path:
    """
    Resolve a user-supplied relative path and ensure it stays inside REPO_PATH.
    Prevents path traversal attacks (../../etc/passwd etc).
    """
    repo = settings.repo_path.resolve()
    # Disallow absolute paths from user
    if Path(user_path).is_absolute():
        raise HTTPException(status_code=400, detail="Absolute paths are not allowed")

    target = (repo / user_path).resolve()

    try:
        target.relative_to(repo)
    except ValueError:
        raise HTTPException(
            status_code=403,
            detail="Path escapes the repository sandbox",
        )
    return target


def require_write(settings: Settings) -> None:
    if not settings.allow_write:
        raise HTTPException(status_code=403, detail="Write operations are disabled (ALLOW_WRITE=false)")


def require_push(settings: Settings) -> None:
    if not settings.allow_push:
        raise HTTPException(status_code=403, detail="Push operations are disabled (ALLOW_PUSH=false)")


def require_quality(settings: Settings) -> None:
    if not settings.allow_quality_commands:
        raise HTTPException(status_code=403, detail="Quality commands are disabled")


def require_branch_ops(settings: Settings) -> None:
    if not settings.allow_branch_ops:
        raise HTTPException(status_code=403, detail="Branch operations are disabled (ALLOW_BRANCH_OPS=false)")


def require_git_mode(settings: Settings) -> None:
    if not settings.is_git_mode:
        raise HTTPException(
            status_code=403,
            detail="This endpoint requires MODE=git. Current mode is 'folder'.",
        )
