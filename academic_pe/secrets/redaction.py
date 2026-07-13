"""Compatibility exports for the redaction API moved to ``academic_pe.core``."""

from academic_pe.core.redaction import REDACTED, SecretRedactionFilter, redact

__all__ = ["REDACTED", "SecretRedactionFilter", "redact"]
