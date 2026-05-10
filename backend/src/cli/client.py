"""HTTP client para a API do backend transcriptor.

Convenções:
- Header `X-API-Key` em toda chamada quando `api_key` está setado.
- 3 tentativas com backoff exponencial em 5xx ou timeout.
- Zero retry em 4xx.
- Erros 401/403 viram `AuthError`; demais erros HTTP viram `ApiError`.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Optional

import httpx


class ApiError(RuntimeError):
    """Falha de chamada HTTP (4xx exceto auth, 5xx após retries, timeouts)."""


class AuthError(ApiError):
    """401 ou 403 do backend."""


_MAX_ATTEMPTS = 3
_BACKOFF_BASE_S = 0.5


class TranscriptorClient:
    def __init__(
        self,
        base_url: str,
        api_key: Optional[str],
        timeout: float = 60.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._client = httpx.Client(timeout=timeout)

    # --- low-level ---

    def _headers(self) -> dict[str, str]:
        return {"X-API-Key": self.api_key} if self.api_key else {}

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        url = f"{self.base_url}{path}"
        headers = {**self._headers(), **kwargs.pop("headers", {})}

        last_exc: Optional[Exception] = None
        for attempt in range(_MAX_ATTEMPTS):
            try:
                response = self._client.request(method, url, headers=headers, **kwargs)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_exc = exc
                if attempt + 1 < _MAX_ATTEMPTS:
                    time.sleep(_BACKOFF_BASE_S * (2**attempt))
                    continue
                raise ApiError(f"network error after {_MAX_ATTEMPTS} attempts: {exc}") from exc

            if response.status_code in (401, 403):
                raise AuthError(f"auth failed: HTTP {response.status_code}")
            if 500 <= response.status_code < 600:
                if attempt + 1 < _MAX_ATTEMPTS:
                    time.sleep(_BACKOFF_BASE_S * (2**attempt))
                    continue
                raise ApiError(f"server error: HTTP {response.status_code}")
            if response.status_code >= 400:
                raise ApiError(f"HTTP {response.status_code}: {response.text[:200]}")
            return response

        raise ApiError(f"unreachable: {last_exc}")

    # --- high-level ---

    def submit(self, audio_path: Path) -> dict[str, Any]:
        """POST /api/transcribe (multipart com `file`). Retorna body JSON."""
        with audio_path.open("rb") as fh:
            files = {"file": (audio_path.name, fh, "application/octet-stream")}
            response = self._request("POST", "/api/transcribe", files=files)
        return response.json()

    def get_status(self, job_id: str) -> dict[str, Any]:
        return self._request("GET", f"/api/transcribe/{job_id}/status").json()

    def get_detail(self, job_id: str) -> dict[str, Any]:
        return self._request("GET", f"/api/transcribe/{job_id}").json()

    def list_jobs(self, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        return self._request(
            "GET",
            "/api/history",
            params={"limit": limit, "offset": offset},
        ).json()

    def delete_job(self, job_id: str) -> None:
        self._request("DELETE", f"/api/transcribe/{job_id}")

    def download_artifact(self, job_id: str, fmt: str, dest: Path) -> Path:
        response = self._request(
            "GET",
            f"/api/transcribe/{job_id}/download",
            params={"format": fmt},
        )
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(response.content)
        return dest

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "TranscriptorClient":
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.close()
