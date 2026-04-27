"""API key authentication middleware.

When TRANSCRIPTOR_API_KEY is set, every request to /api/* must provide the
key in the X-API-Key header. Endpoints that browsers reach without custom
headers (SSE progress streams, direct download links) also accept the key
via an `api_key` query parameter. Non-/api paths (the SPA at / and assets
under /static) are never challenged.
"""

import os
import secrets
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


_QUERY_PARAM_PATHS = ("/progress", "/download")


def _extract_provided_key(request: Request) -> Optional[str]:
    header_key = request.headers.get("X-API-Key")
    if header_key:
        return header_key
    if request.url.path.endswith(_QUERY_PARAM_PATHS):
        return request.query_params.get("api_key")
    return None


def install_api_key_auth(app: FastAPI, api_key: Optional[str] = None) -> None:
    """Attach the auth middleware to the app.

    If `api_key` is None, no challenge is issued — useful for local dev and
    for the existing test suite that does not set the env var.
    """

    @app.middleware("http")
    async def api_key_middleware(request: Request, call_next):
        if not api_key:
            return await call_next(request)
        if not request.url.path.startswith("/api/"):
            return await call_next(request)
        provided = _extract_provided_key(request)
        if provided is None or not secrets.compare_digest(provided, api_key):
            return JSONResponse(
                status_code=401,
                content={
                    "error_code": "unauthorized",
                    "message": "Missing or invalid API key.",
                    "details": None,
                },
            )
        return await call_next(request)


def get_configured_api_key() -> Optional[str]:
    """Read the API key from the environment. Empty string -> None."""
    value = os.environ.get("TRANSCRIPTOR_API_KEY", "").strip()
    return value or None
