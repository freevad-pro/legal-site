"""Структурированные события скана.

Живут в отдельном модуле, чтобы `app.engine` и `app.scan_state` не образовали
циклический импорт через общий тип события.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

EventType = Literal[
    "scanner_started",
    "scanner_done",
    "violation_evaluated",
    "done",
    "error",
]


class ScanEvent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    type: EventType
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    payload: dict[str, Any] = Field(default_factory=dict)
