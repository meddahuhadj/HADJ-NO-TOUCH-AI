"""HADJ Action History.

A local, thread-safe log of every action the system took (real or
simulated) together with lightweight analytics: what was executed most,
which input sources were used, and accuracy over the last actions.
Nothing sensitive is stored beyond the action label.
"""

from __future__ import annotations

import threading
import time
from collections import Counter, deque
from dataclasses import dataclass, field


# status values
STATUS_OK = "OK"
STATUS_SIMULATED = "SIMULATED"
STATUS_BLOCKED = "BLOCKED"
STATUS_FAILED = "FAILED"
STATUS_CONFIRMED = "CONFIRMED"


@dataclass
class ActionRecord:
    ts: float = field(default_factory=time.monotonic)
    source: str = "system"      # voice / gesture / custom / macro / ai / planner / head
    action: str = ""            # human-readable label
    status: str = STATUS_OK
    params: dict = field(default_factory=dict)
    simulated: bool = False

    def as_dict(self) -> dict:
        return {
            "ts": self.ts,
            "source": self.source,
            "action": self.action,
            "status": self.status,
            "params": dict(self.params),
            "simulated": self.simulated,
        }


class ActionHistory:
    def __init__(self, maxlen: int = 250) -> None:
        self._items: deque[ActionRecord] = deque(maxlen=maxlen)
        self._lock = threading.RLock()

    def record(self, source: str, action: str, params: dict | None = None,
               status: str = STATUS_OK, simulated: bool = False) -> ActionRecord:
        rec = ActionRecord(source=source, action=action,
                           params=dict(params or {}), status=status,
                           simulated=simulated)
        with self._lock:
            self._items.append(rec)
        return rec

    def recent(self, n: int = 30) -> list[dict]:
        with self._lock:
            return [r.as_dict() for r in list(self._items)[-n:]]

    def clear(self) -> None:
        with self._lock:
            self._items.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)

    def analytics(self) -> dict:
        """Local statistics over the retained window (no data leaves device)."""
        with self._lock:
            items = list(self._items)
        if not items:
            return {
                "actions": 0, "by_action": {}, "by_source": {},
                "by_status": {}, "accuracy": 1.0, "false_triggers": 0,
            }
        by_action = Counter(r.action for r in items)
        by_source = Counter(r.source for r in items)
        by_status = Counter(r.status for r in items)
        total = len(items)
        successful = by_status.get(STATUS_OK, 0) + by_status.get(STATUS_CONFIRMED, 0)
        return {
            "actions": total,
            "by_action": dict(by_action.most_common(12)),
            "by_source": dict(by_source.most_common()),
            "by_status": dict(by_status),
            "accuracy": round(successful / total, 3),
            "false_triggers": int(by_status.get(STATUS_BLOCKED, 0)),
        }


TIMESTAMP_FMT = "%H:%M:%S"


def format_record(rec: dict) -> str:
    import datetime
    stamp = datetime.datetime.fromtimestamp(rec.get("ts", 0)).strftime(TIMESTAMP_FMT)
    return f"{stamp}  {rec.get('source','?'):<8} {rec.get('status','?')}  {rec.get('action','')}"