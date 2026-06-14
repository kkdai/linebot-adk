"""Endpoint-level tests for main.py with heavy clients patched out."""
import sys
import types as pytypes

import pytest

from firestore_store import Store
from tests.fake_firestore import FakeFirestore


@pytest.fixture
def client(monkeypatch):
    # Env required at import time.
    monkeypatch.setenv("ChannelSecret", "secret")
    monkeypatch.setenv("ChannelAccessToken", "token")
    monkeypatch.setenv("GOOGLE_API_KEY", "key")
    monkeypatch.setenv("TasksToken", "tasktoken")

    # Stub firestore.Client so default_store() doesn't touch GCP.
    fake_db = FakeFirestore()
    fake_firestore_mod = pytypes.ModuleType("google.cloud.firestore")
    fake_firestore_mod.Client = lambda *a, **k: fake_db
    monkeypatch.setitem(sys.modules, "google.cloud.firestore", fake_firestore_mod)

    sys.modules.pop("main", None)
    import main

    from fastapi.testclient import TestClient

    return TestClient(main.app), main, Store(fake_db)


def test_health(client):
    tc, _, _ = client
    assert tc.get("/health").json() == {"status": "ok"}


def test_webhook_missing_signature_returns_400(client):
    tc, _, _ = client
    assert tc.post("/", content=b"{}").status_code == 400


def test_task_endpoint_requires_token(client):
    tc, _, _ = client
    assert tc.post("/tasks/morning-reminder").status_code == 401
    assert tc.post(
        "/tasks/morning-reminder", headers={"X-Tasks-Token": "wrong"}
    ).status_code == 401


def test_morning_reminder_with_token(client):
    tc, main, store = client
    fam = store.create_family(elder_id="e1")
    store.create_user("e1", "elder")
    store.set_user_family("e1", fam)

    pushed = []

    async def fake_push(uid, text):
        pushed.append(uid)

    main.push_text = fake_push  # also patch the symbol tasks call receives
    resp = tc.post("/tasks/morning-reminder", headers={"X-Tasks-Token": "tasktoken"})
    assert resp.status_code == 200
    assert resp.json() == {"reminded": 1}
    assert pushed == ["e1"]
