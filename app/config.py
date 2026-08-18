from pathlib import Path
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Auth
    nova_api_key: str = Field(..., min_length=16)

    # Repo
    repo_path: Path
    port: int = 8080
    host: str = "127.0.0.1"

    # Timeouts & limits
    idle_timeout_minutes: int = 30
    max_file_size_mb: int = 5
    rate_limit_per_minute: int = 30

    # Mode:
    #   auto   = file ops always; git endpoints if path is a git repo (recommended)
    #   git    = require valid git repo (fail startup/ops if not)
    #   folder = file ops only (git endpoints disabled)
    mode: str = "auto"

    # Feature flags
    allow_write: bool = True
    allow_push: bool = True
    allow_quality_commands: bool = True
    allow_branch_ops: bool = True  # create / delete / checkout / rename branch

    # Optional GitHub token (stays on server only)
    github_token: str | None = None

    # Tunnel
    tunnel_provider: str = "cloudflare"  # cloudflare | ngrok | none
    cloudflare_tunnel_name: str | None = None
    cloudflare_credentials_file: str | None = None
    ngrok_authtoken: str | None = None
    ngrok_domain: str | None = None

    # Logging
    log_level: str = "INFO"
    audit_log_file: Path = Path("./logs/audit.log")

    @field_validator("repo_path")
    @classmethod
    def validate_repo_path(cls, v: Path) -> Path:
        path = v.expanduser().resolve()
        if not path.exists():
            raise ValueError(f"REPO_PATH does not exist: {path}")
        if not path.is_dir():
            raise ValueError(f"REPO_PATH is not a directory: {path}")
        return path

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        v = v.lower().strip()
        if v not in ("auto", "git", "folder"):
            raise ValueError("MODE must be 'auto', 'git', or 'folder'")
        return v

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024

    @property
    def git_repo_detected(self) -> bool:
        """True if REPO_PATH looks like a git working tree."""
        try:
            return (self.repo_path / ".git").exists()
        except Exception:
            return False

    @property
    def is_git_mode(self) -> bool:
        """
        Whether git endpoints are available.
        - auto: enable if .git exists
        - git: always treat as git (GitService will error if invalid)
        - folder: never
        """
        if self.mode == "folder":
            return False
        if self.mode == "git":
            return True
        # auto
        return self.git_repo_detected


@lru_cache
def get_settings() -> Settings:
    return Settings()
