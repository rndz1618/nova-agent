from pathlib import Path
from typing import Any
import git
from git.exc import GitCommandError, InvalidGitRepositoryError
from fastapi import HTTPException
from .config import Settings


class GitService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.repo_path = settings.repo_path
        try:
            self.repo = git.Repo(self.repo_path)
        except InvalidGitRepositoryError:
            raise HTTPException(
                status_code=500,
                detail=f"Not a valid git repository: {self.repo_path}",
            )

    def status(self) -> dict[str, Any]:
        return {
            "branch": self.repo.active_branch.name if not self.repo.head.is_detached else "DETACHED",
            "is_dirty": self.repo.is_dirty(untracked_files=True),
            "untracked": self.repo.untracked_files,
            "modified": [item.a_path for item in self.repo.index.diff(None)],
            "staged": [item.a_path for item in self.repo.index.diff("HEAD")],
            "ahead_behind": self._ahead_behind(),
        }

    def _ahead_behind(self) -> dict[str, int]:
        try:
            branch = self.repo.active_branch
            tracking = branch.tracking_branch()
            if tracking is None:
                return {"ahead": 0, "behind": 0}
            ahead = len(list(self.repo.iter_commits(f"{tracking}..{branch}")))
            behind = len(list(self.repo.iter_commits(f"{branch}..{tracking}")))
            return {"ahead": ahead, "behind": behind}
        except Exception:
            return {"ahead": 0, "behind": 0}

    def diff(self, staged: bool = False) -> str:
        if staged:
            return self.repo.git.diff("--cached")
        return self.repo.git.diff()

    def log(self, max_count: int = 20) -> list[dict[str, str]]:
        commits = list(self.repo.iter_commits(max_count=max_count))
        return [
            {
                "hash": c.hexsha[:8],
                "full_hash": c.hexsha,
                "author": str(c.author),
                "date": c.committed_datetime.isoformat(),
                "message": c.message.strip(),
            }
            for c in commits
        ]

    def show(self, rev: str = "HEAD") -> str:
        try:
            return self.repo.git.show(rev, "--stat")
        except GitCommandError as e:
            raise HTTPException(status_code=400, detail=str(e))

    def branch_list(self) -> dict[str, Any]:
        local = [b.name for b in self.repo.branches]
        remote = [r.name for r in self.repo.remotes.origin.refs] if self.repo.remotes else []
        return {
            "current": self.repo.active_branch.name if not self.repo.head.is_detached else None,
            "local": local,
            "remote": remote,
        }

    def commit(self, message: str, add_all: bool = True) -> dict[str, str]:
        if not message or not message.strip():
            raise HTTPException(status_code=400, detail="Commit message is required")

        if add_all:
            self.repo.git.add(A=True)

        if not self.repo.is_dirty(index=True, working_tree=False, untracked_files=False):
            # nothing staged
            if not self.repo.is_dirty(untracked_files=True):
                raise HTTPException(status_code=400, detail="Nothing to commit")

        try:
            commit = self.repo.index.commit(message.strip())
            return {
                "hash": commit.hexsha[:8],
                "full_hash": commit.hexsha,
                "message": commit.message.strip(),
            }
        except GitCommandError as e:
            raise HTTPException(status_code=400, detail=str(e))

    def push(self, remote: str = "origin", branch: str | None = None) -> str:
        try:
            if branch is None:
                branch = self.repo.active_branch.name
            # Prefer token if available (for HTTPS remotes)
            if self.settings.github_token:
                # Note: for security we do not rewrite remote URL permanently
                result = self.repo.git.push(remote, branch)
            else:
                result = self.repo.git.push(remote, branch)
            return result or "Push successful"
        except GitCommandError as e:
            raise HTTPException(status_code=400, detail=f"Push failed: {e}")

    def pull(self, remote: str = "origin", branch: str | None = None) -> str:
        try:
            if branch is None:
                branch = self.repo.active_branch.name
            result = self.repo.git.pull(remote, branch)
            return result or "Pull successful"
        except GitCommandError as e:
            raise HTTPException(status_code=400, detail=f"Pull failed: {e}")

    # -------------------- Branch management --------------------

    def create_branch(self, name: str, start_point: str | None = None) -> dict[str, str]:
        if not name or not name.strip():
            raise HTTPException(status_code=400, detail="Branch name is required")
        name = name.strip()
        try:
            if start_point:
                new_branch = self.repo.create_head(name, commit=start_point)
            else:
                new_branch = self.repo.create_head(name)
            return {"name": new_branch.name, "message": f"Branch '{name}' created"}
        except GitCommandError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to create branch: {e}")

    def checkout_branch(self, name: str, create: bool = False) -> dict[str, str]:
        if not name or not name.strip():
            raise HTTPException(status_code=400, detail="Branch name is required")
        name = name.strip()
        try:
            if create:
                self.repo.git.checkout("-b", name)
            else:
                self.repo.git.checkout(name)
            return {"name": name, "message": f"Checked out branch '{name}'"}
        except GitCommandError as e:
            raise HTTPException(status_code=400, detail=str(e))

    def delete_branch(self, name: str, force: bool = False) -> dict[str, str]:
        if not name or not name.strip():
            raise HTTPException(status_code=400, detail="Branch name is required")
        name = name.strip()

        # Safety: never delete the currently checked-out branch
        try:
            current = self.repo.active_branch.name
            if name == current:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot delete the currently checked-out branch '{name}'. Switch first.",
                )
        except TypeError:
            # detached HEAD
            pass

        try:
            args = ["-D" if force else "-d", name]
            self.repo.git.branch(*args)
            return {"name": name, "message": f"Branch '{name}' deleted"}
        except GitCommandError as e:
            raise HTTPException(status_code=400, detail=str(e))

    def rename_branch(self, old_name: str, new_name: str) -> dict[str, str]:
        if not old_name or not new_name:
            raise HTTPException(status_code=400, detail="Both old_name and new_name are required")
        old_name, new_name = old_name.strip(), new_name.strip()
        try:
            self.repo.git.branch("-m", old_name, new_name)
            return {
                "old_name": old_name,
                "new_name": new_name,
                "message": f"Branch renamed from '{old_name}' to '{new_name}'",
            }
        except GitCommandError as e:
            raise HTTPException(status_code=400, detail=str(e))
