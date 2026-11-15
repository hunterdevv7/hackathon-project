"""Hardening behaviour of the API: JSON-only errors, CORS off by default, body limits."""
import json

import pytest

from backend import config
from backend.app import create_app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(config, "QUANTUM_MODE", "mock")
    monkeypatch.setattr(config, "CORS_ORIGINS", [])
    return create_app().test_client()


def test_404_is_json(client):
    resp = client.get("/no-such-route")
    assert resp.status_code == 404
    assert resp.get_json() == {"error": "Not Found"}
    assert resp.mimetype == "application/json"


def test_405_is_json(client):
    resp = client.post("/engine")
    assert resp.status_code == 405
    assert resp.get_json() == {"error": "Method Not Allowed"}


def test_oversized_body_is_413_json(client):
    body = json.dumps({"bits": [0] * 200_000})  # ~600 KB, far above MAX_BODY_BYTES
    resp = client.post("/attack", data=body, content_type="application/json")
    assert resp.status_code == 413
    assert resp.get_json() == {"error": "Request Entity Too Large"}


def test_no_cors_header_by_default(client):
    resp = client.get("/engine", headers={"Origin": "http://evil.example"})
    assert resp.status_code == 200
    assert "Access-Control-Allow-Origin" not in resp.headers


def test_cors_only_for_configured_origins(monkeypatch):
    monkeypatch.setattr(config, "QUANTUM_MODE", "mock")
    monkeypatch.setattr(config, "CORS_ORIGINS", ["http://localhost:8080"])
    client = create_app().test_client()
    ok = client.get("/engine", headers={"Origin": "http://localhost:8080"})
    assert ok.headers.get("Access-Control-Allow-Origin") == "http://localhost:8080"
    other = client.get("/engine", headers={"Origin": "http://evil.example"})
    assert "Access-Control-Allow-Origin" not in other.headers


def test_dotfiles_are_not_served(client):
    assert client.get("/assets/.env").status_code == 404
    assert client.get("/assets/../.env").status_code == 404
