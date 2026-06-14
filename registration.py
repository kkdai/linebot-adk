"""Pairing-code registration and binding between relatives and elders.

Flow: a relative requests a code; the elder enters the code to bind. All
relatives who bind end up in the elder's family.
"""
from __future__ import annotations

import datetime
import random
from dataclasses import dataclass
from typing import Optional

from firestore_store import Store

CODE_TTL_MINUTES = 30
ROLE_ELDER = "elder"
ROLE_RELATIVE = "relative"

CODE_RE_LEN = 6


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def generate_code() -> str:
    return f"{random.randint(0, 999999):06d}"


def register_relative(store: Store, uid: str, display_name: str = "") -> str:
    """Register the user as a relative and return a fresh pairing code."""
    user = store.get_user(uid)
    if user is None:
        store.create_user(uid, ROLE_RELATIVE, display_name)
    elif user.get("role") != ROLE_RELATIVE:
        store.set_user_role(uid, ROLE_RELATIVE)

    code = generate_code()
    expires_at = (_now() + datetime.timedelta(minutes=CODE_TTL_MINUTES)).isoformat()
    store.create_pairing_code(code, uid, expires_at)
    return code


def register_elder(store: Store, uid: str, display_name: str = "") -> None:
    """Mark the user as an elder (does not bind yet)."""
    user = store.get_user(uid)
    if user is None:
        store.create_user(uid, ROLE_ELDER, display_name)
    elif user.get("role") != ROLE_ELDER:
        store.set_user_role(uid, ROLE_ELDER)


@dataclass
class BindResult:
    ok: bool
    reason: Optional[str] = None  # "not_found" | "used" | "expired"
    relative_id: Optional[str] = None
    family_id: Optional[str] = None


def is_pairing_code(text: str) -> bool:
    return text.strip().isdigit() and len(text.strip()) == CODE_RE_LEN


def bind_with_code(
    store: Store, elder_uid: str, code: str, display_name: str = ""
) -> BindResult:
    """Bind the elder to the relative behind ``code``."""
    code = code.strip()
    entry = store.get_pairing_code(code)
    if entry is None:
        return BindResult(ok=False, reason="not_found")
    if entry.get("used"):
        return BindResult(ok=False, reason="used")
    try:
        expires_at = datetime.datetime.fromisoformat(entry["expiresAt"])
    except (KeyError, ValueError):
        return BindResult(ok=False, reason="expired")
    if _now() > expires_at:
        return BindResult(ok=False, reason="expired")

    relative_id = entry["relativeId"]

    # Ensure the elder exists and is marked as elder.
    elder = store.get_user(elder_uid)
    if elder is None:
        store.create_user(elder_uid, ROLE_ELDER, display_name)
        elder = store.get_user(elder_uid)
    elif elder.get("role") != ROLE_ELDER:
        store.set_user_role(elder_uid, ROLE_ELDER)
        elder["role"] = ROLE_ELDER

    # Ensure the elder has a family.
    family_id = elder.get("familyId")
    if not family_id:
        family_id = store.create_family(elder_id=elder_uid)
        store.set_user_family(elder_uid, family_id)
    else:
        store.set_family_elder(family_id, elder_uid)

    # Attach the relative to the elder's family.
    store.add_relative_to_family(family_id, relative_id)
    store.set_user_family(relative_id, family_id)
    store.mark_pairing_code_used(code)

    return BindResult(
        ok=True, relative_id=relative_id, family_id=family_id
    )
