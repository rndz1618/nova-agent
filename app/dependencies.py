"""Shared FastAPI dependencies (single source of truth)."""

from typing import Annotated

from fastapi import Depends

from .config import get_settings, Settings
from .security import require_git_mode
from .git_ops import GitService
from .quality import QualityService
from .file_ops import FileService
from .audit import get_audit_logger, AuditLogger


def get_file_svc(settings: Annotated[Settings, Depends(get_settings)]) -> FileService:
    return FileService(settings)


def get_git_svc(settings: Annotated[Settings, Depends(get_settings)]) -> GitService:
    require_git_mode(settings)
    return GitService(settings)


def get_quality_svc(settings: Annotated[Settings, Depends(get_settings)]) -> QualityService:
    require_git_mode(settings)
    return QualityService(settings)


def get_audit(settings: Annotated[Settings, Depends(get_settings)]) -> AuditLogger:
    return get_audit_logger(settings)
