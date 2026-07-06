"""Helpers for keeping SmartHub secrets out of logs and diagnostics."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from typing import Any

SENSITIVE_KEYS = {
    "access_token",
    "accesstoken",
    "authorization",
    "authorization_token",
    "authorizationtoken",
    "bearer",
    "password",
    "token",
}

PARTIAL_SENSITIVE_KEYS = {
    "account",
    "meter",
    "service_location",
    "servicelocation",
    "userid",
    "username",
    "user_id",
}

EMAIL_RE = re.compile(
    r"(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
)
BEARER_RE = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE)
KEY_VALUE_SECRET_RE = re.compile(
    r"\b(password|passwd|token|access_token|accessToken|authorizationToken)"
    r"\s*[:=]\s*['\"]?[^,\s'\"}]+",
    re.IGNORECASE,
)
LONG_NUMBER_RE = re.compile(r"\b\d{5,}\b")


def redact_value(value: Any) -> Any:
    """Redact secrets and account identifiers from log-safe values."""
    if isinstance(value, Mapping):
        return {
            key: _redact_by_key(str(key), nested_value)
            for key, nested_value in value.items()
        }

    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [redact_value(item) for item in value]

    if isinstance(value, str):
        return _redact_text(value)

    return value


def redact_for_log(value: Any, max_length: int = 500) -> str:
    """Return a compact redacted string suitable for logs."""
    redacted = redact_value(value)
    if isinstance(redacted, str):
        text = redacted
    else:
        try:
            text = json.dumps(redacted, sort_keys=True, default=str)
        except TypeError:
            text = str(redacted)
    text = _redact_text(text)

    if len(text) > max_length:
        return f"{text[:max_length]}..."
    return text


def mask_identifier(value: Any) -> str:
    """Mask an identifier while preserving a short suffix for troubleshooting."""
    return _mask_identifier(value)


def _redact_by_key(key: str, value: Any) -> Any:
    normalized = re.sub(r"[^a-z0-9]", "", key.lower())
    if normalized in SENSITIVE_KEYS:
        return "***REDACTED***"
    if any(partial in normalized for partial in PARTIAL_SENSITIVE_KEYS):
        return _mask_identifier(value)
    return redact_value(value)


def _mask_identifier(value: Any) -> str:
    text = str(value)
    if len(text) <= 4:
        return "***REDACTED***"
    return f"***REDACTED***{text[-4:]}"


def _redact_text(text: str) -> str:
    text = BEARER_RE.sub("Bearer ***REDACTED***", text)
    text = KEY_VALUE_SECRET_RE.sub(r"\1=***REDACTED***", text)
    text = EMAIL_RE.sub("***REDACTED_EMAIL***", text)
    text = LONG_NUMBER_RE.sub("***REDACTED_NUMBER***", text)
    return text
