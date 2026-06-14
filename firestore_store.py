"""Firestore data access for the blood-pressure reminder bot.

The :class:`Store` takes an injected Firestore client so it can be unit-tested
with an in-memory fake. Use :func:`default_store` to build one backed by the
real ``google.cloud.firestore`` client at runtime.
"""
from __future__ import annotations

import uuid
from typing import Optional


def _query_where(collection, field: str, op: str, value):
    """Apply a where filter, using FieldFilter when firestore is available."""
    try:
        from google.cloud.firestore_v1.base_query import FieldFilter

        return collection.where(filter=FieldFilter(field, op, value))
    except ImportError:
        return collection.where(field, op, value)


class Store:
    USERS = "users"
    FAMILIES = "families"
    PAIRING = "pairingCodes"
    RECORDS = "records"

    def __init__(self, db):
        self.db = db

    # --- users -----------------------------------------------------------
    def get_user(self, uid: str) -> Optional[dict]:
        snap = self.db.collection(self.USERS).document(uid).get()
        return snap.to_dict() if snap.exists else None

    def create_user(self, uid: str, role: str, display_name: str = "") -> dict:
        data = {
            "role": role,
            "displayName": display_name,
            "familyId": None,
            "createdAt": _now_iso(),
        }
        self.db.collection(self.USERS).document(uid).set(data)
        return data

    def set_user_role(self, uid: str, role: str) -> None:
        self.db.collection(self.USERS).document(uid).update({"role": role})

    def set_user_family(self, uid: str, family_id: str) -> None:
        self.db.collection(self.USERS).document(uid).update({"familyId": family_id})

    def list_elders(self) -> list[dict]:
        coll = self.db.collection(self.USERS)
        out = []
        for snap in _query_where(coll, "role", "==", "elder").stream():
            d = snap.to_dict()
            d["uid"] = snap.id
            out.append(d)
        return out

    # --- families --------------------------------------------------------
    def create_family(self, elder_id: Optional[str] = None) -> str:
        family_id = uuid.uuid4().hex[:12]
        self.db.collection(self.FAMILIES).document(family_id).set(
            {
                "elderId": elder_id,
                "relativeIds": [],
                "createdAt": _now_iso(),
            }
        )
        return family_id

    def get_family(self, family_id: str) -> Optional[dict]:
        snap = self.db.collection(self.FAMILIES).document(family_id).get()
        return snap.to_dict() if snap.exists else None

    def set_family_elder(self, family_id: str, elder_id: str) -> None:
        self.db.collection(self.FAMILIES).document(family_id).update(
            {"elderId": elder_id}
        )

    def add_relative_to_family(self, family_id: str, relative_id: str) -> None:
        family = self.get_family(family_id) or {"relativeIds": []}
        relatives = list(family.get("relativeIds") or [])
        if relative_id not in relatives:
            relatives.append(relative_id)
        self.db.collection(self.FAMILIES).document(family_id).update(
            {"relativeIds": relatives}
        )

    # --- pairing codes ---------------------------------------------------
    def create_pairing_code(
        self, code: str, relative_id: str, expires_at_iso: str
    ) -> None:
        self.db.collection(self.PAIRING).document(code).set(
            {
                "relativeId": relative_id,
                "expiresAt": expires_at_iso,
                "used": False,
                "createdAt": _now_iso(),
            }
        )

    def get_pairing_code(self, code: str) -> Optional[dict]:
        snap = self.db.collection(self.PAIRING).document(code).get()
        return snap.to_dict() if snap.exists else None

    def mark_pairing_code_used(self, code: str) -> None:
        self.db.collection(self.PAIRING).document(code).update({"used": True})

    # --- records ---------------------------------------------------------
    def add_record(
        self,
        family_id: str,
        elder_id: str,
        date: str,
        systolic: int,
        diastolic: int,
        pulse: Optional[int],
        category: str,
        source: str,
    ) -> str:
        record_id = uuid.uuid4().hex
        self.db.collection(self.RECORDS).document(record_id).set(
            {
                "familyId": family_id,
                "elderId": elder_id,
                "date": date,
                "systolic": systolic,
                "diastolic": diastolic,
                "pulse": pulse,
                "category": category,
                "source": source,
                "createdAt": _now_iso(),
            }
        )
        return record_id

    def has_record_on(self, elder_id: str, date: str) -> bool:
        coll = self.db.collection(self.RECORDS)
        q = _query_where(coll, "elderId", "==", elder_id)
        q = _query_where(q, "date", "==", date)
        for _ in q.limit(1).stream():
            return True
        return False

    def list_records(self, elder_id: str, since_date: str) -> list[dict]:
        coll = self.db.collection(self.RECORDS)
        q = _query_where(coll, "elderId", "==", elder_id)
        out = []
        for snap in q.stream():
            d = snap.to_dict()
            if d.get("date", "") >= since_date:
                out.append(d)
        out.sort(key=lambda r: r.get("createdAt", ""))
        return out


def _now_iso() -> str:
    import datetime

    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def default_store() -> Store:
    """Build a Store backed by the real Firestore client (lazy import)."""
    from google.cloud import firestore

    return Store(firestore.Client())
