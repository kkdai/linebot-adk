"""Scheduled-task logic: morning reminders and escalation to relatives.

Both functions take an async ``push(uid, text)`` callback so they can be tested
without LINE.
"""
from __future__ import annotations

from typing import Awaitable, Callable

from firestore_store import Store

PushFn = Callable[[str, str], Awaitable[None]]

MORNING_REMINDER_TEXT = (
    "🌞 早安！記得今天要量血壓喔～\n"
    "量好後直接傳數值（例如 120/80）或拍血壓計照片給我就可以了。"
)


def _escalation_text(elder_name: str) -> str:
    who = elder_name or "長輩"
    return f"📣 提醒您：{who} 今天還沒有量血壓，方便的話請關心一下他喔。"


async def run_morning_reminder(store: Store, today: str, push: PushFn) -> int:
    """Remind every elder who has no reading today. Returns count reminded."""
    count = 0
    for elder in store.list_elders():
        if store.has_record_on(elder["uid"], today):
            continue
        await push(elder["uid"], MORNING_REMINDER_TEXT)
        count += 1
    return count


async def run_escalation_check(store: Store, today: str, push: PushFn) -> int:
    """Notify relatives of every elder still without a reading today.

    Returns the number of relative notifications sent.
    """
    sent = 0
    for elder in store.list_elders():
        if store.has_record_on(elder["uid"], today):
            continue
        family_id = elder.get("familyId")
        if not family_id:
            continue
        family = store.get_family(family_id) or {}
        text = _escalation_text(elder.get("displayName", ""))
        for relative_id in family.get("relativeIds") or []:
            await push(relative_id, text)
            sent += 1
    return sent
