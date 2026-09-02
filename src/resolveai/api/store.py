"""In-memory index of incident_id -> graph thread config.

Deliberately not the checkpointer itself (that already persists full graph
state) -- this is just the thin lookup table the API needs to know which
thread_id an incident_id maps to, and to serve a cheap status list without
round-tripping the checkpointer for every request.
"""

from __future__ import annotations

import threading


class IncidentIndex:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._incident_ids: list[str] = []

    def add(self, incident_id: str) -> None:
        with self._lock:
            if incident_id not in self._incident_ids:
                self._incident_ids.append(incident_id)

    def list_ids(self) -> list[str]:
        with self._lock:
            return list(self._incident_ids)
