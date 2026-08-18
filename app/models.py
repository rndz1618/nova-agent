from pydantic import BaseModel, Field


class WriteFileRequest(BaseModel):
    path: str = Field(..., min_length=1, max_length=512)
    content: str = Field(..., max_length=5_000_000)


class CommitRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=500)
    add_all: bool = True


class PushPullRequest(BaseModel):
    remote: str = "origin"
    branch: str | None = None


class QualityRequest(BaseModel):
    command: str = Field(..., description="One of: pytest, ruff, ruff-format-check, mypy, black-check")


class CreateBranchRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    start_point: str | None = None


class CheckoutRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    create: bool = False


class DeleteBranchRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    force: bool = False


class RenameBranchRequest(BaseModel):
    old_name: str = Field(..., min_length=1, max_length=200)
    new_name: str = Field(..., min_length=1, max_length=200)
