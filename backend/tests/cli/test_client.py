from pathlib import Path

import httpx
import pytest
import respx

from src.cli.client import TranscriptorClient, ApiError, AuthError


@pytest.fixture
def client():
    return TranscriptorClient(base_url="http://test", api_key="K")


@respx.mock
def test_submit_uploads_file_with_apikey_header(tmp_path: Path, client: TranscriptorClient):
    audio = tmp_path / "a.mp3"
    audio.write_bytes(b"\xff\xfb_fake_mp3")

    route = respx.post("http://test/api/transcribe").mock(
        return_value=httpx.Response(202, json={"id": "j1", "status": "pending", "filename": "a.mp3", "position": 0})
    )

    job = client.submit(audio)

    assert job["id"] == "j1"
    assert route.called
    sent = route.calls.last.request
    assert sent.headers["X-API-Key"] == "K"
    assert b"a.mp3" in sent.content


@respx.mock
def test_get_status_returns_payload(client: TranscriptorClient):
    respx.get("http://test/api/transcribe/j1/status").mock(
        return_value=httpx.Response(200, json={"id": "j1", "status": "completed", "current_stage": "complete", "error_message": None})
    )
    status = client.get_status("j1")
    assert status["status"] == "completed"


@respx.mock
def test_list_jobs_supports_limit_offset(client: TranscriptorClient):
    route = respx.get("http://test/api/history").mock(
        return_value=httpx.Response(200, json={"total": 0, "items": []})
    )
    client.list_jobs(limit=10, offset=20)
    assert route.calls.last.request.url.params["limit"] == "10"
    assert route.calls.last.request.url.params["offset"] == "20"


@respx.mock
def test_delete_job_calls_delete(client: TranscriptorClient):
    route = respx.delete("http://test/api/transcribe/j1").mock(
        return_value=httpx.Response(204)
    )
    client.delete_job("j1")
    assert route.called


@respx.mock
def test_download_artifact_writes_file(tmp_path: Path, client: TranscriptorClient):
    respx.get("http://test/api/transcribe/j1/download").mock(
        return_value=httpx.Response(200, text="SUBTITLE BODY")
    )
    dest = tmp_path / "out.srt"
    client.download_artifact("j1", "srt", dest)
    assert dest.read_text() == "SUBTITLE BODY"


@respx.mock
def test_401_raises_autherror(client: TranscriptorClient):
    respx.get("http://test/api/transcribe/j1/status").mock(
        return_value=httpx.Response(401, json={"error_code": "unauthorized", "message": "x"})
    )
    with pytest.raises(AuthError):
        client.get_status("j1")


@respx.mock
def test_5xx_retries_then_raises_apierror(client: TranscriptorClient):
    route = respx.get("http://test/api/transcribe/j1/status").mock(
        return_value=httpx.Response(503)
    )
    with pytest.raises(ApiError):
        client.get_status("j1")
    assert route.call_count == 3  # 1 + 2 retries


@respx.mock
def test_4xx_does_not_retry(client: TranscriptorClient):
    route = respx.get("http://test/api/transcribe/j1/status").mock(
        return_value=httpx.Response(404, json={"detail": "not found"})
    )
    with pytest.raises(ApiError):
        client.get_status("j1")
    assert route.call_count == 1


def test_init_strips_trailing_slash():
    c = TranscriptorClient(base_url="http://x:9/", api_key=None)
    assert c.base_url == "http://x:9"
