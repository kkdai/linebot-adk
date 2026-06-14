"""Minimal in-memory Firestore double for unit tests.

Implements just the surface the Store uses: collection/document/get/set/update,
positional where(), limit(), and stream().
"""
from __future__ import annotations

import copy
import uuid


class _Snapshot:
    def __init__(self, doc_id, data):
        self.id = doc_id
        self._data = data

    @property
    def exists(self):
        return self._data is not None

    def to_dict(self):
        return copy.deepcopy(self._data) if self._data is not None else None


class _DocRef:
    def __init__(self, collection, doc_id):
        self._collection = collection
        self.id = doc_id

    def get(self):
        return _Snapshot(self.id, self._collection._docs.get(self.id))

    def set(self, data):
        self._collection._docs[self.id] = copy.deepcopy(data)

    def update(self, data):
        existing = self._collection._docs.setdefault(self.id, {})
        existing.update(copy.deepcopy(data))


class _Query:
    def __init__(self, collection, filters):
        self._collection = collection
        self._filters = filters
        self._limit = None

    def where(self, field=None, op=None, value=None, filter=None):
        field, op, value = _normalize_where(field, op, value, filter)
        assert op == "=="
        return _Query(self._collection, self._filters + [(field, value)])

    def limit(self, n):
        self._limit = n
        return self

    def stream(self):
        count = 0
        for doc_id, data in self._collection._docs.items():
            if all(data.get(f) == v for f, v in self._filters):
                yield _Snapshot(doc_id, data)
                count += 1
                if self._limit is not None and count >= self._limit:
                    return


class _Collection:
    def __init__(self):
        self._docs = {}

    def document(self, doc_id=None):
        if doc_id is None:
            doc_id = uuid.uuid4().hex
        return _DocRef(self, doc_id)

    def where(self, field=None, op=None, value=None, filter=None):
        field, op, value = _normalize_where(field, op, value, filter)
        return _Query(self, []).where(field, op, value)

    def stream(self):
        return _Query(self, []).stream()


def _normalize_where(field, op, value, filter):
    """Support both positional where() and where(filter=FieldFilter(...))."""
    if filter is not None:
        return filter.field_path, filter.op_string, filter.value
    return field, op, value


class FakeFirestore:
    def __init__(self):
        self._collections = {}

    def collection(self, name):
        return self._collections.setdefault(name, _Collection())
