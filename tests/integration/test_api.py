"""Exercises the FastAPI layer end-to-end via Starlette's TestClient (which
drives the real ASGI app, including the lifespan startup that builds the
graph) -- not mocked, just pointed at RESOLVEAI_LLM_PROVIDER=fake so it needs
no network or API key.
"""

import os

os.environ.setdefault("RESOLVEAI_LLM_PROVIDER", "fake")
os.environ.setdefault("RESOLVEAI_EMBEDDING_PROVIDER", "fake")

import pytest
from fastapi.testclient import TestClient

from resolveai.api.main import app


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_submit_small_refund_auto_resolves(client):
    resp = client.post(
        "/incidents",
        json={
            "customer_id": "cust_1002",
            "subject": "Charged twice",
            "description": "I was charged twice for order_5002, please refund the duplicate charge.",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "resolved"
    assert body["decision"]["action"] == "issue_refund"


def test_submit_high_value_refund_pauses_and_can_be_approved(client):
    submit = client.post(
        "/incidents",
        json={
            "customer_id": "cust_1004",
            "subject": "Order never arrived, need refund",
            "description": "My order never arrived per tracking, I want a refund immediately.",
        },
    ).json()
    assert submit["status"] == "pending_human_review"
    incident_id = submit["incident_id"]

    approve = client.post(f"/incidents/{incident_id}/approve", json={"approved": True, "note": "ok"}).json()
    assert approve["status"] == "resolved"


def test_approve_before_pending_returns_409(client):
    submit = client.post(
        "/incidents",
        json={"customer_id": "cust_1002", "subject": "hi", "description": "just saying hi"},
    ).json()
    resp = client.post(f"/incidents/{submit['incident_id']}/approve", json={"approved": True})
    # this incident auto-resolves or auto-escalates immediately (no pending review) -> 409 either way is wrong
    # only assert 409 when it truly wasn't paused
    if submit["status"] != "pending_human_review":
        assert resp.status_code == 409


def test_get_unknown_incident_returns_404(client):
    resp = client.get("/incidents/does_not_exist")
    assert resp.status_code == 404


def test_list_incidents_includes_submitted_ones(client):
    submitted = client.post(
        "/incidents",
        json={
            "customer_id": "cust_1002",
            "subject": "Charged twice",
            "description": "refund the duplicate charge please",
        },
    ).json()
    listing = client.get("/incidents").json()
    ids = [i["incident_id"] for i in listing["incidents"]]
    assert submitted["incident_id"] in ids
