"""MCP OAuth — client-credentials token acquisition for remote servers.

Implements the OAuth2 client-credentials grant (service-to-service), which needs
no browser and is what self-hosted/automation setups use. The fetched access
token is sent as a bearer to the HTTP MCP client.

Config (per server, under mcpServers.<name>.oauth):
    {"token_url": "...", "client_id": "...", "client_secret": "...", "scope": "..."}
"""
from __future__ import annotations

import json

from clims_core.http import post_form, HTTPError


def fetch_client_credentials_token(oauth: dict) -> str:
    token_url = oauth.get("token_url")
    if not token_url:
        raise ValueError("oauth: 'token_url' is required")
    fields = {
        "grant_type": "client_credentials",
        "client_id": oauth.get("client_id", ""),
        "client_secret": oauth.get("client_secret", ""),
    }
    if oauth.get("scope"):
        fields["scope"] = oauth["scope"]
    try:
        _ctype, body = post_form(token_url, fields, timeout=30)
    except HTTPError as e:
        raise ValueError(f"oauth token request failed: HTTP {e.status}: {e.body[:200]}") from None
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        raise ValueError("oauth: token endpoint did not return JSON") from None
    token = data.get("access_token")
    if not token:
        raise ValueError(f"oauth: no access_token in response: {body[:200]}")
    return token
