from pathlib import Path
from typing import Any
from fastapi import HTTPException
from .config import Settings
from .security import safe_resolve_path


class FileService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.repo = settings.repo_path

    def list_dir(self, relative_path: str = ".") -> list[dict[str, Any]]:
        target = safe_resolve_path(relative_path, self.settings)
        if not target.exists():
            raise HTTPException(status_code=404, detail="Path not found")
        if not target.is_dir():
            raise HTTPException(status_code=400, detail="Path is not a directory")

        items = []
        for p in sorted(target.iterdir()):
            # Skip .git for safety & noise
            if p.name == ".git":
                continue
            items.append({
                "name": p.name,
                "path": str(p.relative_to(self.repo)),
                "is_dir": p.is_dir(),
                "size": p.stat().st_size if p.is_file() else None,
            })
        return items

    def read_file(self, relative_path: str) -> dict[str, Any]:
        target = safe_resolve_path(relative_path, self.settings)
        if not target.exists():
            raise HTTPException(status_code=404, detail="File not found")
        if not target.is_file():
            raise HTTPException(status_code=400, detail="Path is not a file")

        size = target.stat().st_size
        if size > self.settings.max_file_size_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"File too large ({size} bytes). Max allowed: {self.settings.max_file_size_bytes}",
            )

        try:
            content = target.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="File is not valid UTF-8 text")

        return {
            "path": relative_path,
            "size": size,
            "content": content,
        }

    def write_file(self, relative_path: str, content: str) -> dict[str, Any]:
        if len(content.encode("utf-8")) > self.settings.max_file_size_bytes:
            raise HTTPException(status_code=413, detail="Content exceeds max file size")

        target = safe_resolve_path(relative_path, self.settings)

        # Create parent directories if needed (still inside sandbox)
        target.parent.mkdir(parents=True, exist_ok=True)

        target.write_text(content, encoding="utf-8")
        return {
            "path": relative_path,
            "size": target.stat().st_size,
            "message": "File written successfully",
        }

    def delete_file(self, relative_path: str) -> dict[str, str]:
        target = safe_resolve_path(relative_path, self.settings)
        if not target.exists():
            raise HTTPException(status_code=404, detail="File not found")
        if target.is_dir():
            raise HTTPException(status_code=400, detail="Refusing to delete directories (safety)")

        target.unlink()
        return {"path": relative_path, "message": "File deleted"}
