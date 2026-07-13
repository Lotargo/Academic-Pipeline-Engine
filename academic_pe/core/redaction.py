from __future__ import annotations

import logging
import re
from typing import Any


REDACTED = "[REDACTED]"
_SENSITIVE = re.compile(r"(?i)(api[_-]?key|authorization|credential|password|secret|token)")
_BEARER = re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/-]+=*")
_ASSIGNMENT = re.compile(
    r"(?i)\b(api[_-]?key|authorization|credential|password|secret|token)\b(\s*[:=]\s*)([^\s,;]+)"
)


def redact(value: Any) -> Any:
    """Remove known credential-bearing values before crossing a log/audit boundary."""

    if isinstance(value, dict):
        return {
            key: REDACTED if _SENSITIVE.search(str(key)) else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return type(value)(redact(item) for item in value)
    if isinstance(value, str):
        value = _BEARER.sub(f"Bearer {REDACTED}", value)
        return _ASSIGNMENT.sub(lambda match: f"{match.group(1)}{match.group(2)}{REDACTED}", value)
    return value


class SecretRedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(record.msg)
        if record.args:
            record.args = redact(record.args)
        return True
