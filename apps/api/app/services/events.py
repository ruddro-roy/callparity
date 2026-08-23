from __future__ import annotations

import json
import threading
from collections import defaultdict
from typing import Any

_lock = threading.Lock()
_events: dict[str, list[dict[str, Any]]] = defaultdict(list)


def publish(ticket_id: str, event: dict[str, Any]) -> None:
    with _lock:
        _events[ticket_id].append(event)


def snapshot(ticket_id: str) -> list[dict[str, Any]]:
    with _lock:
        return list(_events[ticket_id])


def encode(event: dict[str, Any]) -> str:
    return f"data: {json.dumps(event, default=str)}\n\n"
