import datetime

import pytest

import registration
from firestore_store import Store
from registration import (
    register_relative,
    register_elder,
    bind_with_code,
    is_pairing_code,
    ROLE_ELDER,
    ROLE_RELATIVE,
)
from tests.fake_firestore import FakeFirestore


@pytest.fixture
def store():
    return Store(FakeFirestore())


# --- Store basics --------------------------------------------------------

def test_user_crud(store):
    assert store.get_user("u1") is None
    store.create_user("u1", ROLE_ELDER, "Grandpa")
    u = store.get_user("u1")
    assert u["role"] == ROLE_ELDER and u["displayName"] == "Grandpa"
    store.set_user_family("u1", "fam1")
    assert store.get_user("u1")["familyId"] == "fam1"


def test_records_and_has_record_on(store):
    fam = store.create_family(elder_id="e1")
    assert store.has_record_on("e1", "2026-06-14") is False
    store.add_record(fam, "e1", "2026-06-14", 120, 80, 70, "正常", "text")
    assert store.has_record_on("e1", "2026-06-14") is True
    assert store.has_record_on("e1", "2026-06-13") is False


def test_list_elders(store):
    store.create_user("e1", ROLE_ELDER)
    store.create_user("e2", ROLE_ELDER)
    store.create_user("r1", ROLE_RELATIVE)
    elders = {e["uid"] for e in store.list_elders()}
    assert elders == {"e1", "e2"}


def test_list_records_since(store):
    fam = store.create_family(elder_id="e1")
    store.add_record(fam, "e1", "2026-06-10", 120, 80, None, "正常", "text")
    store.add_record(fam, "e1", "2026-06-14", 130, 85, None, "高血壓一期", "text")
    recs = store.list_records("e1", "2026-06-12")
    assert len(recs) == 1 and recs[0]["date"] == "2026-06-14"


# --- Registration & binding ---------------------------------------------

def test_is_pairing_code():
    assert is_pairing_code("123456")
    assert is_pairing_code(" 123456 ")
    assert not is_pairing_code("12345")
    assert not is_pairing_code("abcdef")


def test_register_relative_creates_user_and_code(store):
    code = register_relative(store, "r1", "Daughter")
    assert is_pairing_code(code)
    assert store.get_user("r1")["role"] == ROLE_RELATIVE
    entry = store.get_pairing_code(code)
    assert entry["relativeId"] == "r1" and entry["used"] is False


def test_full_bind_flow(store):
    code = register_relative(store, "r1", "Daughter")
    register_elder(store, "e1", "Grandpa")
    result = bind_with_code(store, "e1", code)
    assert result.ok
    fam = store.get_family(result.family_id)
    assert fam["elderId"] == "e1"
    assert "r1" in fam["relativeIds"]
    assert store.get_user("e1")["familyId"] == result.family_id
    assert store.get_user("r1")["familyId"] == result.family_id


def test_multiple_relatives_join_same_family(store):
    code1 = register_relative(store, "r1")
    register_elder(store, "e1")
    r1 = bind_with_code(store, "e1", code1)
    code2 = register_relative(store, "r2")
    r2 = bind_with_code(store, "e1", code2)
    assert r1.family_id == r2.family_id
    fam = store.get_family(r1.family_id)
    assert set(fam["relativeIds"]) == {"r1", "r2"}


def test_bind_unknown_code(store):
    res = bind_with_code(store, "e1", "000000")
    assert not res.ok and res.reason == "not_found"


def test_bind_used_code(store):
    code = register_relative(store, "r1")
    bind_with_code(store, "e1", code)
    res = bind_with_code(store, "e2", code)
    assert not res.ok and res.reason == "used"


def test_bind_expired_code(store, monkeypatch):
    code = register_relative(store, "r1")
    # Move time forward beyond TTL.
    real_now = registration._now()
    future = real_now + datetime.timedelta(minutes=registration.CODE_TTL_MINUTES + 1)
    monkeypatch.setattr(registration, "_now", lambda: future)
    res = bind_with_code(store, "e1", code)
    assert not res.ok and res.reason == "expired"


def test_bind_without_explicit_elder_registration(store):
    code = register_relative(store, "r1")
    res = bind_with_code(store, "e1", code, display_name="Grandpa")
    assert res.ok
    assert store.get_user("e1")["role"] == ROLE_ELDER
