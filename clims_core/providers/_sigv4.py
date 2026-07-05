"""AWS Signature Version 4 signing (stdlib only) — for Bedrock routing.

Implements the canonical request → string-to-sign → signing-key → signature flow.
Verified against AWS's documented GET ListUsers test vector (see tests).
"""
from __future__ import annotations

import hashlib
import hmac
import urllib.parse

ALGORITHM = "AWS4-HMAC-SHA256"


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hmac(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _signing_key(secret: str, datestamp: str, region: str, service: str) -> bytes:
    k_date = _hmac(("AWS4" + secret).encode("utf-8"), datestamp)
    k_region = _hmac(k_date, region)
    k_service = _hmac(k_region, service)
    return _hmac(k_service, "aws4_request")


def canonical_request(method: str, url: str, headers: dict, payload: bytes) -> tuple[str, str]:
    parsed = urllib.parse.urlsplit(url)
    canonical_uri = parsed.path or "/"
    # canonical query string: sorted by key, percent-encoded
    qs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    canonical_qs = "&".join(
        f"{urllib.parse.quote(k, safe='~')}={urllib.parse.quote(v, safe='~')}"
        for k, v in sorted(qs))
    lower = {k.lower(): v.strip() for k, v in headers.items()}
    signed_headers = ";".join(sorted(lower))
    canonical_headers = "".join(f"{k}:{lower[k]}\n" for k in sorted(lower))
    cr = "\n".join([
        method, canonical_uri, canonical_qs,
        canonical_headers, signed_headers, _sha256_hex(payload),
    ])
    return cr, signed_headers


def sign(method: str, url: str, region: str, service: str,
         access_key: str, secret_key: str, headers: dict, payload: bytes,
         amz_date: str, session_token: str | None = None) -> dict:
    """Return headers to add (Authorization, X-Amz-Date, etc.). `amz_date` is like
    20150830T123600Z; datestamp derived from its first 8 chars."""
    datestamp = amz_date[:8]
    parsed = urllib.parse.urlsplit(url)
    hdrs = dict(headers)
    hdrs.setdefault("host", parsed.netloc)
    hdrs["x-amz-date"] = amz_date
    if session_token:
        hdrs["x-amz-security-token"] = session_token

    cr, signed_headers = canonical_request(method, url, hdrs, payload)
    scope = f"{datestamp}/{region}/{service}/aws4_request"
    string_to_sign = "\n".join([ALGORITHM, amz_date, scope, _sha256_hex(cr.encode("utf-8"))])
    key = _signing_key(secret_key, datestamp, region, service)
    signature = hmac.new(key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    authorization = (
        f"{ALGORITHM} Credential={access_key}/{scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )
    out = {"Authorization": authorization, "X-Amz-Date": amz_date}
    if session_token:
        out["X-Amz-Security-Token"] = session_token
    return out
