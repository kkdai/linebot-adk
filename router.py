"""Message routing logic for the blood-pressure reminder bot.

Pure-ish handlers that take an injected Store and callbacks, so they can be
unit-tested without LINE, Firestore, or Gemini.
"""
from __future__ import annotations

from typing import Awaitable, Callable, Optional, Tuple

import bp_advice
import registration
from bp_advice import PolishFn
from bp_parser import BPReading, parse_bp
from firestore_store import Store

ROLE_ELDER = registration.ROLE_ELDER
ROLE_RELATIVE = registration.ROLE_RELATIVE

RELATIVE_CMDS = {"我是親屬", "我是家屬", "我是家人", "成為照護者", "照護者"}
ELDER_CMDS = {"我是長輩", "我是阿公", "我是阿嬤", "我是爺爺", "我是奶奶"}
HELP_CMDS = {"說明", "help", "功能", "選單", "?", "？"}
HISTORY_CMDS = {"查血壓", "我的血壓", "血壓紀錄", "歷史", "紀錄"}

HISTORY_DAYS = 7

HELP_TEXT = (
    "🩺 血壓小幫手使用說明\n"
    "・長輩：直接傳血壓數值（例如 120/80）或拍血壓計照片即可記錄。\n"
    "・家屬：輸入「我是親屬」取得配對碼，再請長輩輸入該碼完成綁定。\n"
    "・長輩：輸入「我是長輩」後，輸入家屬給的 6 位數配對碼即可綁定。\n"
    "・輸入「查血壓」可查看最近的紀錄。\n"
    "每天早上會提醒量血壓；若未量測，下午會通知家屬。"
)

# Async callback that produces a conversational reply for fall-through text.
AgentReplyFn = Callable[[str, str], Awaitable[str]]


def _ensure_elder_family(store: Store, uid: str) -> Tuple[str, str]:
    """Return (family_id, elder_id) for recording a reading from ``uid``."""
    user = store.get_user(uid)
    if user is None:
        store.create_user(uid, ROLE_ELDER)
        user = store.get_user(uid)

    family_id = user.get("familyId")
    if user.get("role") == ROLE_RELATIVE and family_id:
        fam = store.get_family(family_id) or {}
        return family_id, (fam.get("elderId") or uid)

    if user.get("role") != ROLE_ELDER:
        store.set_user_role(uid, ROLE_ELDER)
    if not family_id:
        family_id = store.create_family(elder_id=uid)
        store.set_user_family(uid, family_id)
    return family_id, uid


def record_and_advise(
    store: Store,
    uid: str,
    reading: BPReading,
    source: str,
    today: str,
    polish: Optional[PolishFn] = None,
) -> str:
    """Persist a reading and return the advice message."""
    family_id, elder_id = _ensure_elder_family(store, uid)
    category = bp_advice.classify(reading["systolic"], reading["diastolic"])
    store.add_record(
        family_id=family_id,
        elder_id=elder_id,
        date=today,
        systolic=reading["systolic"],
        diastolic=reading["diastolic"],
        pulse=reading.get("pulse"),
        category=category.label,
        source=source,
    )
    return bp_advice.build_advice(reading, polish=polish)


def _history_reply(store: Store, uid: str, today: str) -> str:
    """Format the elder's recent readings."""
    import datetime

    user = store.get_user(uid) or {}
    elder_id = uid
    family_id = user.get("familyId")
    if user.get("role") == ROLE_RELATIVE and family_id:
        fam = store.get_family(family_id) or {}
        elder_id = fam.get("elderId") or uid

    since = (
        datetime.date.fromisoformat(today) - datetime.timedelta(days=HISTORY_DAYS - 1)
    ).isoformat()
    records = store.list_records(elder_id, since)
    if not records:
        return "目前還沒有血壓紀錄喔，量好後傳數值（例如 120/80）給我就會記錄。"

    lines = [f"📒 最近 {HISTORY_DAYS} 天血壓紀錄："]
    for r in records:
        pulse = f"，脈搏 {r['pulse']}" if r.get("pulse") else ""
        lines.append(f"{r['date']}　{r['systolic']}/{r['diastolic']}{pulse}（{r['category']}）")
    return "\n".join(lines)


def _bind_reply(result: registration.BindResult) -> str:
    if result.ok:
        return "✅ 綁定成功！家屬將會在您忘記量血壓時收到提醒。"
    reasons = {
        "not_found": "找不到這組配對碼，請確認後再輸入一次。",
        "used": "這組配對碼已經被使用過了，請家屬重新產生一組。",
        "expired": "這組配對碼已過期，請家屬重新產生一組。",
    }
    return "⚠️ " + reasons.get(result.reason or "", "綁定失敗，請再試一次。")


async def handle_text_message(
    store: Store,
    uid: str,
    text: str,
    today: str,
    *,
    polish: Optional[PolishFn] = None,
    agent_reply: Optional[AgentReplyFn] = None,
) -> str:
    """Route an inbound text message and return the reply text."""
    stripped = text.strip()
    lowered = stripped.lower()

    if lowered in HELP_CMDS or stripped in HELP_CMDS:
        return HELP_TEXT

    if stripped in RELATIVE_CMDS:
        code = registration.register_relative(store, uid)
        return (
            f"請把這組配對碼告訴長輩，請他輸入：\n\n📌 {code}\n\n"
            f"（{registration.CODE_TTL_MINUTES} 分鐘內有效）"
        )

    if stripped in ELDER_CMDS:
        registration.register_elder(store, uid)
        return "好的！請輸入家屬給您的 6 位數配對碼來完成綁定。"

    if stripped in HISTORY_CMDS:
        return _history_reply(store, uid, today)

    if registration.is_pairing_code(stripped):
        result = registration.bind_with_code(store, uid, stripped)
        return _bind_reply(result)

    reading = parse_bp(stripped)
    if reading is not None:
        return record_and_advise(store, uid, reading, "text", today, polish=polish)

    if agent_reply is not None:
        return await agent_reply(stripped, uid)
    return HELP_TEXT
