from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.dashboard_security import (
    install_dashboard_security,
)


def make_app():
    app = FastAPI()

    install_dashboard_security(
        app
    )

    @app.get("/read")
    def read():
        return {
            "ok": True
        }

    @app.post("/write")
    def write():
        return {
            "changed": True
        }

    return app


def test_public_dashboard_allows_reads(
    monkeypatch,
):
    monkeypatch.setenv(
        "PUBLIC_DASHBOARD_READ_ONLY",
        "true",
    )

    client = TestClient(
        make_app()
    )

    response = client.get(
        "/read"
    )

    assert response.status_code == 200
    assert response.json() == {
        "ok": True
    }


def test_public_dashboard_blocks_writes(
    monkeypatch,
):
    monkeypatch.setenv(
        "PUBLIC_DASHBOARD_READ_ONLY",
        "true",
    )

    client = TestClient(
        make_app()
    )

    response = client.post(
        "/write"
    )

    assert response.status_code == 403
    assert (
        response.json()[
            "paperOnly"
        ]
        is True
    )


def test_local_mode_allows_writes(
    monkeypatch,
):
    monkeypatch.delenv(
        "PUBLIC_DASHBOARD_READ_ONLY",
        raising=False,
    )

    client = TestClient(
        make_app()
    )

    response = client.post(
        "/write"
    )

    assert response.status_code == 200
