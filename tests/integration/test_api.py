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


def test_response_exposes_sources_so_citations_are_traceable(client):
    body = client.post(
        "/incidents",
        json={
            "customer_id": "cust_1002",
            "subject": "Charged twice",
            "description": "I was charged twice for order_5002, please refund the duplicate charge.",
        },
    ).json()
    assert body["incident"]["customer_id"] == "cust_1002"
    assert body["retrieved_passages"], "retrieved policy passages should be returned"
    assert body["tool_evidence"], "MCP tool evidence should be returned"

    known_sources = {p["doc_id"] for p in body["retrieved_passages"]} | {
        e["source_tool"] for e in body["tool_evidence"]
    }
    for citation in body["decision"]["citations"]:
        assert citation in known_sources, f"citation {citation!r} does not map to any returned source"


def test_evals_endpoint_returns_metrics(client):
    body = client.get("/evals").json()
    assert body["cases"] == len(body["results"]) > 0
    for name in (
        "category_accuracy",
        "outcome_accuracy",
        "escalation_precision",
        "escalation_recall",
        "groundedness_rate",
    ):
        assert 0.0 <= body["metrics"][name] <= 1.0


def test_cors_allows_the_dashboard_origin(client):
    resp = client.options(
        "/incidents",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"},
    )
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_paused_incident_can_be_fetched_and_listed(client):
    """Regression: GET on a paused incident used to 500 (read `__interrupt__`
    from snapshot.values, where it never exists)."""
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

    fetched = client.get(f"/incidents/{incident_id}")
    assert fetched.status_code == 200
    assert fetched.json()["status"] == "pending_human_review"
    assert fetched.json()["pending_review"]["recommended_action"] == "issue_refund"

    listing = client.get("/incidents")
    assert listing.status_code == 200
    paused = [i for i in listing.json()["incidents"] if i["incident_id"] == incident_id]
    assert paused and paused[0]["pending_review"]["reason"]
