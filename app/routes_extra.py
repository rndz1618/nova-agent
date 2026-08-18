from typing import Annotated
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from .config import get_settings, Settings
from .security import verify_api_key, require_write, require_branch_ops, require_quality
from .audit import get_audit_logger, AuditLogger
from .file_ops import FileService
from .git_ops import GitService
from .quality import QualityService
from .models import (
    QualityRequest,
    CreateBranchRequest,
    CheckoutRequest,
    DeleteBranchRequest,
    RenameBranchRequest,
)

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


def get_git_svc(settings: Annotated[Settings, Depends(get_settings)]) -> GitService:
    from .security import require_git_mode
    require_git_mode(settings)
    return GitService(settings)


def get_quality_svc(settings: Annotated[Settings, Depends(get_settings)]) -> QualityService:
    from .security import require_git_mode
    require_git_mode(settings)
    return QualityService(settings)


def get_audit(settings: Annotated[Settings, Depends(get_settings)]) -> AuditLogger:
    return get_audit_logger(settings)

@router.post("/git/branch/create")
@limiter.limit("10/minute")
async def branch_create(
    request: Request,
    body: CreateBranchRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    _: Annotated[str, Depends(verify_api_key)] = None,
    svc: Annotated[GitService, Depends(get_git_svc)] = None,
    audit: Annotated[AuditLogger, Depends(get_audit)] = None,
):
    require_branch_ops(settings)
    require_write(settings)
    result = svc.create_branch(body.name, start_point=body.start_point)
    audit.log(action="branch_create", detail=body.name, client_ip=request.client.host if request.client else None)
    return result


@router.post("/git/branch/checkout")
@limiter.limit("10/minute")
async def branch_checkout(
    request: Request,
    body: CheckoutRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    _: Annotated[str, Depends(verify_api_key)] = None,
    svc: Annotated[GitService, Depends(get_git_svc)] = None,
    audit: Annotated[AuditLogger, Depends(get_audit)] = None,
):
    require_branch_ops(settings)
    require_write(settings)
    result = svc.checkout_branch(body.name, create=body.create)
    audit.log(action="branch_checkout", detail=body.name, client_ip=request.client.host if request.client else None)
    return result


@router.post("/git/branch/delete")
@limiter.limit("5/minute")
async def branch_delete(
    request: Request,
    body: DeleteBranchRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    _: Annotated[str, Depends(verify_api_key)] = None,
    svc: Annotated[GitService, Depends(get_git_svc)] = None,
    audit: Annotated[AuditLogger, Depends(get_audit)] = None,
):
    require_branch_ops(settings)
    require_write(settings)
    result = svc.delete_branch(body.name, force=body.force)
    audit.log(action="branch_delete", detail=body.name, client_ip=request.client.host if request.client else None)
    return result


@router.post("/git/branch/rename")
@limiter.limit("5/minute")
async def branch_rename(
    request: Request,
    body: RenameBranchRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    _: Annotated[str, Depends(verify_api_key)] = None,
    svc: Annotated[GitService, Depends(get_git_svc)] = None,
    audit: Annotated[AuditLogger, Depends(get_audit)] = None,
):
    require_branch_ops(settings)
    require_write(settings)
    result = svc.rename_branch(body.old_name, body.new_name)
    audit.log(
        action="branch_rename",
        detail=f"{body.old_name} -> {body.new_name}",
        client_ip=request.client.host if request.client else None,
    )
    return result


@router.post("/quality/run")
@limiter.limit("5/minute")
async def run_quality(
    request: Request,
    body: QualityRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    _: Annotated[str, Depends(verify_api_key)] = None,
    svc: Annotated[QualityService, Depends(get_quality_svc)] = None,
    audit: Annotated[AuditLogger, Depends(get_audit)] = None,
):
    require_quality(settings)
    result = svc.run(body.command)
    audit.log(
        action="quality_run",
        detail=body.command,
        success=result["success"],
        client_ip=request.client.host if request.client else None,
    )
    return result


@router.get("/audit")
@limiter.limit("10/minute")
async def get_audit_log(
    request: Request,
    lines: int = 50,
    _: Annotated[str, Depends(verify_api_key)] = None,
    settings: Annotated[Settings, Depends(get_settings)] = None,
):
    import json
    log_file = settings.audit_log_file
    if not log_file.exists():
        return {"entries": []}
    with open(log_file, "r", encoding="utf-8") as f:
        all_lines = f.readlines()
    recent = all_lines[-min(lines, 200) :]
    entries = []
    for line in recent:
        try:
            entries.append(json.loads(line))
        except Exception:
            continue
    return {"entries": entries}
