from typing import Annotated
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from .config import get_settings, Settings
from .security import (
    verify_api_key,
    require_write,
    require_push,
)
from .file_ops import FileService
from .git_ops import GitService
from .audit import AuditLogger
from .dependencies import get_file_svc, get_git_svc, get_audit
from .models import (
    WriteFileRequest,
    CommitRequest,
    PushPullRequest,
)

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


@router.get("/health")
@limiter.limit("10/minute")
async def health(request: Request, settings: Annotated[Settings, Depends(get_settings)]):
    return {
        "status": "ok",
        "time": datetime.now(timezone.utc).isoformat(),
        "mode": settings.mode,
        "git_available": settings.is_git_mode,
        "git_repo_detected": settings.git_repo_detected,
        "path": str(settings.repo_path),
        "idle_timeout_minutes": settings.idle_timeout_minutes,
        "features": {
            "files": True,
            "write": settings.allow_write,
            "git": settings.is_git_mode,
            "push": settings.allow_push and settings.is_git_mode,
            "quality": settings.allow_quality_commands and settings.is_git_mode,
            "branch_ops": settings.allow_branch_ops and settings.is_git_mode,
        },
    }


@router.get("/config")
async def config_info(
    request: Request,
    _: Annotated[str, Depends(verify_api_key)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    return {
        "mode": settings.mode,
        "git_available": settings.is_git_mode,
        "git_repo_detected": settings.git_repo_detected,
        "path": str(settings.repo_path),
        "allow_write": settings.allow_write,
        "allow_push": settings.allow_push,
        "allow_quality": settings.allow_quality_commands,
        "allow_branch_ops": settings.allow_branch_ops,
        "max_file_size_mb": settings.max_file_size_mb,
        "idle_timeout_minutes": settings.idle_timeout_minutes,
        "tunnel_provider": settings.tunnel_provider,
    }


@router.get("/files")
@limiter.limit("30/minute")
async def list_files(
    request: Request,
    path: str = ".",
    _: Annotated[str, Depends(verify_api_key)] = None,
    svc: Annotated[FileService, Depends(get_file_svc)] = None,
    audit: Annotated[AuditLogger, Depends(get_audit)] = None,
):
    result = svc.list_dir(path)
    audit.log(action="list_files", path=path, client_ip=request.client.host if request.client else None)
    return {"path": path, "items": result}


@router.get("/files/content")
@limiter.limit("30/minute")
async def read_file(
    request: Request,
    path: str,
    _: Annotated[str, Depends(verify_api_key)] = None,
    svc: Annotated[FileService, Depends(get_file_svc)] = None,
    audit: Annotated[AuditLogger, Depends(get_audit)] = None,
):
    result = svc.read_file(path)
    audit.log(action="read_file", path=path, client_ip=request.client.host if request.client else None)
    return result


@router.put("/files")
@limiter.limit("20/minute")
async def write_file(
    request: Request,
    body: WriteFileRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    _: Annotated[str, Depends(verify_api_key)] = None,
    svc: Annotated[FileService, Depends(get_file_svc)] = None,
    audit: Annotated[AuditLogger, Depends(get_audit)] = None,
):
    require_write(settings)
    result = svc.write_file(body.path, body.content)
    audit.log(action="write_file", path=body.path, client_ip=request.client.host if request.client else None)
    return result


@router.delete("/files")
@limiter.limit("10/minute")
async def delete_file(
    request: Request,
    path: str,
    settings: Annotated[Settings, Depends(get_settings)],
    _: Annotated[str, Depends(verify_api_key)] = None,
    svc: Annotated[FileService, Depends(get_file_svc)] = None,
    audit: Annotated[AuditLogger, Depends(get_audit)] = None,
):
    require_write(settings)
    result = svc.delete_file(path)
    audit.log(action="delete_file", path=path, client_ip=request.client.host if request.client else None)
    return result


@router.get("/git/status")
@limiter.limit("30/minute")
async def git_status(
    request: Request,
    _: Annotated[str, Depends(verify_api_key)] = None,
    svc: Annotated[GitService, Depends(get_git_svc)] = None,
    audit: Annotated[AuditLogger, Depends(get_audit)] = None,
):
    result = svc.status()
    audit.log(action="git_status", client_ip=request.client.host if request.client else None)
    return result


@router.get("/git/diff")
@limiter.limit("20/minute")
async def git_diff(
    request: Request,
    staged: bool = False,
    _: Annotated[str, Depends(verify_api_key)] = None,
    svc: Annotated[GitService, Depends(get_git_svc)] = None,
):
    return {"diff": svc.diff(staged=staged)}


@router.get("/git/log")
@limiter.limit("20/minute")
async def git_log(
    request: Request,
    max_count: int = 20,
    _: Annotated[str, Depends(verify_api_key)] = None,
    svc: Annotated[GitService, Depends(get_git_svc)] = None,
):
    return {"commits": svc.log(max_count=min(max_count, 50))}


@router.get("/git/show")
@limiter.limit("20/minute")
async def git_show(
    request: Request,
    rev: str = "HEAD",
    _: Annotated[str, Depends(verify_api_key)] = None,
    svc: Annotated[GitService, Depends(get_git_svc)] = None,
):
    return {"show": svc.show(rev)}


@router.get("/git/branch")
@limiter.limit("20/minute")
async def git_branch(
    request: Request,
    _: Annotated[str, Depends(verify_api_key)] = None,
    svc: Annotated[GitService, Depends(get_git_svc)] = None,
):
    return svc.branch_list()


@router.post("/git/commit")
@limiter.limit("10/minute")
async def git_commit(
    request: Request,
    body: CommitRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    _: Annotated[str, Depends(verify_api_key)] = None,
    svc: Annotated[GitService, Depends(get_git_svc)] = None,
    audit: Annotated[AuditLogger, Depends(get_audit)] = None,
):
    require_write(settings)
    result = svc.commit(body.message, add_all=body.add_all)
    audit.log(
        action="git_commit",
        detail=body.message,
        client_ip=request.client.host if request.client else None,
        extra={"hash": result["hash"]},
    )
    return result


@router.post("/git/push")
@limiter.limit("5/minute")
async def git_push(
    request: Request,
    body: PushPullRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    _: Annotated[str, Depends(verify_api_key)] = None,
    svc: Annotated[GitService, Depends(get_git_svc)] = None,
    audit: Annotated[AuditLogger, Depends(get_audit)] = None,
):
    require_push(settings)
    result = svc.push(remote=body.remote, branch=body.branch)
    audit.log(action="git_push", detail=result, client_ip=request.client.host if request.client else None)
    return {"message": result}


@router.post("/git/pull")
@limiter.limit("10/minute")
async def git_pull(
    request: Request,
    body: PushPullRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    _: Annotated[str, Depends(verify_api_key)] = None,
    svc: Annotated[GitService, Depends(get_git_svc)] = None,
    audit: Annotated[AuditLogger, Depends(get_audit)] = None,
):
    require_write(settings)
    result = svc.pull(remote=body.remote, branch=body.branch)
    audit.log(action="git_pull", detail=result, client_ip=request.client.host if request.client else None)
    return {"message": result}
