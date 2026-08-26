"""Sanitized, checkpointed live-run support independent of experiment domain."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def sanitize_error_detail(detail: str) -> str:
    redacted = re.sub(r"user_[A-Za-z0-9_-]+", "[REDACTED_USER]", detail)
    redacted = re.sub(r"sk-[A-Za-z0-9_-]+", "[REDACTED_KEY]", redacted)
    return redacted[:1_000]


def checkpoint_json(output: Path, report: dict[str, Any]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    report["updated_at"] = datetime.now(UTC).isoformat()
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
