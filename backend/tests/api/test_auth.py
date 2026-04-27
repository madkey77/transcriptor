from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.auth import install_api_key_auth


def make_app(api_key: str | None) -> TestClient:
    app = FastAPI()
    install_api_key_auth(app, api_key=api_key)

    @app.get("/api/protected")
    def protected():
        return {"ok": True}

    @app.get("/api/transcribe/abc/progress")
    def progress():
        return {"streaming": True}

    @app.get("/")
    def index():
        return {"page": "index"}

    @app.get("/static/app.js")
    def static_file():
        return {"asset": True}

    return TestClient(app)


def test_no_key_configured_allows_all_requests():
    client = make_app(api_key=None)
    assert client.get("/api/protected").status_code == 200
    assert client.get("/").status_code == 200


def test_api_route_requires_header_when_key_configured():
    client = make_app(api_key="secret123")
    r = client.get("/api/protected")
    assert r.status_code == 401
    assert r.json()["error_code"] == "unauthorized"


def test_api_route_accepts_correct_header():
    client = make_app(api_key="secret123")
    r = client.get("/api/protected", headers={"X-API-Key": "secret123"})
    assert r.status_code == 200


def test_api_route_rejects_wrong_header():
    client = make_app(api_key="secret123")
    r = client.get("/api/protected", headers={"X-API-Key": "nope"})
    assert r.status_code == 401


def test_progress_endpoint_accepts_query_param():
    client = make_app(api_key="secret123")
    r = client.get("/api/transcribe/abc/progress?api_key=secret123")
    assert r.status_code == 200


def test_progress_endpoint_rejects_wrong_query_param():
    client = make_app(api_key="secret123")
    r = client.get("/api/transcribe/abc/progress?api_key=wrong")
    assert r.status_code == 401


def test_non_api_paths_skip_auth_when_key_configured():
    client = make_app(api_key="secret123")
    assert client.get("/").status_code == 200
    assert client.get("/static/app.js").status_code == 200
