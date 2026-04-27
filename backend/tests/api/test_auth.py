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


def test_get_configured_api_key_reads_env(monkeypatch):
    from src.api.auth import get_configured_api_key

    monkeypatch.delenv("TRANSCRIPTOR_API_KEY", raising=False)
    assert get_configured_api_key() is None

    monkeypatch.setenv("TRANSCRIPTOR_API_KEY", "  ")
    assert get_configured_api_key() is None

    monkeypatch.setenv("TRANSCRIPTOR_API_KEY", "real-key")
    assert get_configured_api_key() == "real-key"


def test_setup_middleware_installs_auth_with_configured_key(monkeypatch):
    """setup_middleware should pull the key from env and challenge requests."""
    monkeypatch.setenv("TRANSCRIPTOR_API_KEY", "live-secret")

    from fastapi import FastAPI
    from src.api.middleware import setup_middleware

    app = FastAPI()
    setup_middleware(app)

    @app.get("/api/ping")
    def ping():
        return {"ok": True}

    client = TestClient(app)
    assert client.get("/api/ping").status_code == 401
    assert client.get("/api/ping", headers={"X-API-Key": "live-secret"}).status_code == 200
