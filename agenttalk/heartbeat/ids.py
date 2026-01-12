from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4


def _ts(dt: datetime) -> str:
    return dt.strftime("%Y%m%dT%H%M%SZ")


@dataclass(frozen=True)
class IdGenerator:
    def new_alert_id(self, now: datetime) -> str:
        return f"alert_{_ts(now)}_{uuid4().hex[:8]}"

    def new_human_request_id(self, now: datetime) -> str:
        return f"human_req_{_ts(now)}_{uuid4().hex[:8]}"

