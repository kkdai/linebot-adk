import re

import pytest

import router
from firestore_store import Store
from router import handle_text_message, record_and_advise, HELP_TEXT
from tests.fake_firestore import FakeFirestore

TODAY = "2026-06-14"


@pytest.fixture
def store():
    return Store(FakeFirestore())


async def _run(store, uid, text, **kw):
    return await handle_text_message(store, uid, text, TODAY, **kw)


@pytest.mark.asyncio
async def test_help_command(store):
    assert await _run(store, "u1", "說明") == HELP_TEXT
    assert await _run(store, "u1", "help") == HELP_TEXT


@pytest.mark.asyncio
async def test_relative_registration_returns_code(store):
    reply = await _run(store, "r1", "我是親屬")
    assert "配對碼" in reply
    assert store.get_user("r1")["role"] == "relative"


@pytest.mark.asyncio
async def test_elder_registration(store):
    reply = await _run(store, "e1", "我是長輩")
    assert "配對碼" in reply
    assert store.get_user("e1")["role"] == "elder"


@pytest.mark.asyncio
async def test_full_binding_via_router(store):
    code_reply = await _run(store, "r1", "我是親屬")
    code = re.search(r"\d{6}", code_reply).group(0)
    reply = await _run(store, "e1", code)
    assert "綁定成功" in reply
    fam_id = store.get_user("e1")["familyId"]
    assert "r1" in store.get_family(fam_id)["relativeIds"]


@pytest.mark.asyncio
async def test_bad_code_message(store):
    reply = await _run(store, "e1", "000000")
    assert "找不到" in reply


@pytest.mark.asyncio
async def test_text_bp_records_and_advises(store):
    reply = await _run(store, "e1", "今天血壓 145/95 脈搏 72")
    assert "高血壓" in reply
    assert store.has_record_on("e1", TODAY)


@pytest.mark.asyncio
async def test_crisis_bp_warns(store):
    reply = await _run(store, "e1", "190/125")
    assert "危象" in reply or "就醫" in reply


@pytest.mark.asyncio
async def test_fallthrough_to_agent(store):
    async def agent(text, uid):
        return f"echo:{text}"

    reply = await _run(store, "u1", "今天天氣如何", agent_reply=agent)
    assert reply == "echo:今天天氣如何"


@pytest.mark.asyncio
async def test_fallthrough_without_agent_returns_help(store):
    reply = await _run(store, "u1", "隨便聊聊")
    assert reply == HELP_TEXT


@pytest.mark.asyncio
async def test_polish_callback_used(store):
    def polish(base_text, category):
        return "潤飾:" + category.label

    reply = await _run(store, "e1", "120/80", polish=polish)
    assert reply.startswith("潤飾:")


@pytest.mark.asyncio
async def test_history_empty(store):
    reply = await _run(store, "e1", "查血壓")
    assert "還沒有血壓紀錄" in reply


@pytest.mark.asyncio
async def test_history_lists_records(store):
    await _run(store, "e1", "120/80")
    await _run(store, "e1", "145/95")
    reply = await _run(store, "e1", "查血壓")
    assert "120/80" in reply and "145/95" in reply


def test_record_and_advise_relative_logs_for_elder(store):
    # Set up a bound family: elder e1, relative r1.
    fam = store.create_family(elder_id="e1")
    store.create_user("e1", "elder")
    store.set_user_family("e1", fam)
    store.create_user("r1", "relative")
    store.set_user_family("r1", fam)
    record_and_advise(store, "r1", {"systolic": 120, "diastolic": 80, "pulse": None}, "text", TODAY)
    # Recorded under the elder, not the relative.
    assert store.has_record_on("e1", TODAY)
    assert store.has_record_on("r1", TODAY) is False
