import json

import httpx
import respx

from src.cli.app import app


@respx.mock
def test_jobs_list_emits_summaries(cli_runner):
    respx.get("http://srv/api/history").mock(
        return_value=httpx.Response(200, json={
            "total": 2,
            "items": [
                {"id": "j1", "filename": "a.mp3", "status": "completed", "created_at": "2026-01-01T00:00:00", "speaker_count": 2},
                {"id": "j2", "filename": "b.mp3", "status": "failed", "created_at": "2026-01-02T00:00:00", "speaker_count": None},
            ],
        })
    )
    result = cli_runner.invoke(app, ["jobs", "list", "--server", "http://srv"])
    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout.strip())
    assert payload["total"] == 2
    assert payload["items"][0]["id"] == "j1"


@respx.mock
def test_jobs_list_passes_limit_offset(cli_runner):
    route = respx.get("http://srv/api/history").mock(
        return_value=httpx.Response(200, json={"total": 0, "items": []})
    )
    cli_runner.invoke(app, ["jobs", "list", "--server", "http://srv", "--limit", "5", "--offset", "10"])
    assert route.calls.last.request.url.params["limit"] == "5"
    assert route.calls.last.request.url.params["offset"] == "10"


@respx.mock
def test_jobs_get_returns_detail(cli_runner):
    respx.get("http://srv/api/transcribe/j1").mock(
        return_value=httpx.Response(200, json={
            "id": "j1", "filename": "a.mp3", "file_size": 100, "upload_timestamp": "x",
            "status": "completed", "error_message": None,
            "created_at": "x", "updated_at": "x",
            "segments": [], "speakers": [],
        })
    )
    result = cli_runner.invoke(app, ["jobs", "get", "j1", "--server", "http://srv"])
    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout.strip())
    assert payload["id"] == "j1"


@respx.mock
def test_jobs_get_with_download_writes_files(cli_runner, tmp_path):
    respx.get("http://srv/api/transcribe/j1").mock(
        return_value=httpx.Response(200, json={
            "id": "j1", "filename": "a.mp3", "file_size": 100, "upload_timestamp": "x",
            "status": "completed", "error_message": None,
            "created_at": "x", "updated_at": "x",
            "segments": [], "speakers": [],
        })
    )
    respx.get("http://srv/api/transcribe/j1/download").mock(
        return_value=httpx.Response(200, text="SRT")
    )
    result = cli_runner.invoke(app, [
        "jobs", "get", "j1",
        "--server", "http://srv",
        "--download",
        "--formats", "srt",
        "--output-dir", str(tmp_path / "out"),
    ])
    assert result.exit_code == 0, result.stderr
    assert (tmp_path / "out" / "a.srt").read_text() == "SRT"


@respx.mock
def test_jobs_delete_with_yes_calls_delete(cli_runner):
    route = respx.delete("http://srv/api/transcribe/j1").mock(
        return_value=httpx.Response(204)
    )
    result = cli_runner.invoke(app, ["jobs", "delete", "j1", "--server", "http://srv", "--yes"])
    assert result.exit_code == 0, result.stderr
    assert route.called


def test_jobs_delete_without_yes_aborts(cli_runner):
    result = cli_runner.invoke(
        app,
        ["jobs", "delete", "j1", "--server", "http://srv"],
        input="n\n",
    )
    assert result.exit_code != 0
