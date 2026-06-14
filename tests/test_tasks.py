import pytest

from firestore_store import Store
from tasks import run_morning_reminder, run_escalation_check
from tests.fake_firestore import FakeFirestore

TODAY = "2026-06-14"


@pytest.fixture
def store():
    return Store(FakeFirestore())


def _bound_family(store, elder, relatives, elder_name=""):
    fam = store.create_family(elder_id=elder)
    store.create_user(elder, "elder", elder_name)
    store.set_user_family(elder, fam)
    for r in relatives:
        store.create_user(r, "relative")
        store.set_user_family(r, fam)
        store.add_relative_to_family(fam, r)
    return fam


@pytest.mark.asyncio
async def test_morning_reminder_skips_those_with_records(store):
    _bound_family(store, "e1", [])
    fam2 = _bound_family(store, "e2", [])
    store.add_record(fam2, "e2", TODAY, 120, 80, None, "正常", "text")

    pushed = []

    async def push(uid, text):
        pushed.append(uid)

    count = await run_morning_reminder(store, TODAY, push)
    assert count == 1
    assert pushed == ["e1"]


@pytest.mark.asyncio
async def test_escalation_notifies_relatives_of_unmeasured_elders(store):
    _bound_family(store, "e1", ["r1", "r2"], elder_name="阿公")
    fam2 = _bound_family(store, "e2", ["r3"])
    store.add_record(fam2, "e2", TODAY, 120, 80, None, "正常", "text")

    pushed = []

    async def push(uid, text):
        pushed.append((uid, text))

    sent = await run_escalation_check(store, TODAY, push)
    assert sent == 2
    targets = {uid for uid, _ in pushed}
    assert targets == {"r1", "r2"}
    assert "阿公" in pushed[0][1]


@pytest.mark.asyncio
async def test_escalation_no_relatives_no_send(store):
    _bound_family(store, "e1", [])

    async def push(uid, text):
        raise AssertionError("should not push")

    sent = await run_escalation_check(store, TODAY, push)
    assert sent == 0
