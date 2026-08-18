import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import structlog

logger = structlog.get_logger()


class AuditLogger:
    def __init__(self, log_file: Path):
        self.log_file = log_file
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

    def log(
        self,
        *,
        action: str,
        path: str | None = None,
        success: bool = True,
        detail: str | None = None,
        client_ip: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "path": path,
            "success": success,
            "detail": detail,
            "client_ip": client_ip,
            **(extra or {}),
        }
        # Structured console log
        logger.info("audit", **entry)

        # Append to file (one JSON object per line)
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error("failed_to_write_audit_log", error=str(e))


def get_audit_logger(settings) -> AuditLogger:
    return AuditLogger(settings.audit_log_file)
