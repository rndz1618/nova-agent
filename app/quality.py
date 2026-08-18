import subprocess
from pathlib import Path
from fastapi import HTTPException
from .config import Settings


ALLOWED_QUALITY_COMMANDS = {
    "pytest": ["pytest", "-q", "--tb=short"],
    "ruff": ["ruff", "check", "."],
    "ruff-format-check": ["ruff", "format", "--check", "."],
    "mypy": ["mypy", "."],
    "black-check": ["black", "--check", "."],
}


class QualityService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.cwd = settings.repo_path

    def run(self, command_key: str, timeout: int = 120) -> dict:
        if command_key not in ALLOWED_QUALITY_COMMANDS:
            raise HTTPException(
                status_code=400,
                detail=f"Command not allowed. Allowed: {list(ALLOWED_QUALITY_COMMANDS.keys())}",
            )

        cmd = ALLOWED_QUALITY_COMMANDS[command_key]
        try:
            result = subprocess.run(
                cmd,
                cwd=self.cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=False,  # critical for security
            )
            return {
                "command": " ".join(cmd),
                "returncode": result.returncode,
                "stdout": result.stdout[-8000:],  # truncate to avoid huge responses
                "stderr": result.stderr[-4000:],
                "success": result.returncode == 0,
            }
        except subprocess.TimeoutExpired:
            raise HTTPException(status_code=408, detail="Command timed out")
        except FileNotFoundError:
            raise HTTPException(
                status_code=500,
                detail=f"Executable not found. Is '{cmd[0]}' installed?",
            )
