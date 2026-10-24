"""Find and remove credentials before any text is sent to the LLM."""

import re

_PATTERNS = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?(?:-----END [A-Z ]*PRIVATE KEY-----|$)"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{40,}\b"),
    re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"),
    re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9]{32,}\b"),
    re.compile(
        r"""(?i)\b(api[_-]?key|secret|token|passwd|password)\b\s*[:=]\s*["'][^"'\s]{8,}["']"""
    ),
]

REDACTED = "[REDACTED]"


def redact(text: str) -> tuple[str, int]:
    """Return (clean_text, number_of_secrets_replaced)."""
    count = 0
    for pattern in _PATTERNS:
        text, n = pattern.subn(REDACTED, text)
        count += n
    return text, count
