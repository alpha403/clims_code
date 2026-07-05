"""Secret redaction for persisted transcripts.

When a user types a credential into chat (e.g. an MCP token), it would otherwise
land in the sqlite session transcript. We scrub common secret shapes before
persisting so the raw value never hits disk. Conservative patterns only — aimed at
obvious API keys/tokens, not arbitrary text.
"""
from __future__ import annotations

import re

_MASK = "[REDACTED]"

# common provider key / token shapes
_PATTERNS = [
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{10,}"),       # Anthropic
    re.compile(r"sk-[A-Za-z0-9_\-]{16,}"),            # OpenAI/DeepSeek
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),        # GitHub tokens
    re.compile(r"xox[baprs]-[A-Za-z0-9\-]{10,}"),     # Slack tokens
    re.compile(r"AKIA[0-9A-Z]{16}"),                  # AWS access key id
    re.compile(r"AIza[0-9A-Za-z_\-]{30,}"),           # Google API key
    re.compile(r"ya29\.[0-9A-Za-z_\-]{20,}"),         # Google OAuth token
    # generic "key/token/secret/password = <long value>"
    re.compile(r"(?i)\b(?:api[_-]?key|token|secret|password|passwd|bearer)\b\s*[:=]\s*['\"]?([A-Za-z0-9_\-\.]{12,})"),
]


def redact_secrets(text: str) -> str:
    if not text:
        return text
    out = text
    for pat in _PATTERNS:
        if pat.groups:
            out = pat.sub(lambda m: m.group(0).replace(m.group(1), _MASK), out)
        else:
            out = pat.sub(_MASK, out)
    return out
