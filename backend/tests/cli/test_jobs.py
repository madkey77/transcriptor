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
