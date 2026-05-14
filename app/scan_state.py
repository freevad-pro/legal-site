"""In-memory реестр сканов: ScanState + ScanRegistry.

Состояние скана живёт в памяти процесса, никаких записей в БД (vision).
TTL не убивает активные сканы — pending/running всегда защищены.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID, uuid4

from app.events import ScanEvent

logger = logging.getLogger(__name__)

ScanStatus = Literal["pending", "running", "done", "failed", "timeout"]
TERMINAL_STATUSES: frozenset[ScanStatus] = frozenset({"done", "failed", "timeout"})


@dataclass
class ScanState:
    scan_id: UUID
    url: str
    with_llm: bool = False
    status: ScanStatus = "pending"
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None
    last_accessed_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    events: list[ScanEvent] = field(default_factory=list)
    queues: list[asyncio.Queue[ScanEvent | None]] = field(default_factory=list)
    # `result` хранит `app.engine.ScanResult`, но импорт engine сюда внёс бы
    # циклику через типы. Аннотируем как Any и проверяем тип на границе.
    result: object | None = None
    error: str | None = None

    def publish(self, event: ScanEvent) -> None:
        self.events.append(event)
        for queue in self.queues:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:  # pragma: no cover - очереди без лимита
                logger.warning("dropping event for scan %s: queue full", self.scan_id)

    def close_subscribers(self) -> None:
        for queue in self.queues:
            try:
                queue.put_nowait(None)
            except asyncio.QueueFull:  # pragma: no cover
                logger.warning("cannot send sentinel for scan %s: queue full", self.scan_id)

    def is_terminal(self) -> bool:
        return self.status in TERMINAL_STATUSES

    def touch(self) -> None:
        self.last_accessed_at = datetime.now(UTC)


class ScanRegistry:
    """Реестр активных и недавно завершённых сканов."""

    def __init__(self, ttl: timedelta) -> None:
        self._states: dict[UUID, ScanState] = {}
        self._ttl = ttl

    def create(self, url: str, *, with_llm: bool = False) -> ScanState:
        state = ScanState(scan_id=uuid4(), url=url, with_llm=with_llm)
        self._states[state.scan_id] = state
        return state

    def get(self, scan_id: UUID) -> ScanState | None:
        state = self._states.get(scan_id)
        if state is not None:
            state.touch()
        return state

    def purge_expired(self) -> int:
        """Удалить просроченные **терминальные** state'ы. Возвращает счётчик."""

        cutoff = datetime.now(UTC) - self._ttl
        to_delete = [
            scan_id
            for scan_id, state in self._states.items()
            if state.is_terminal() and state.last_accessed_at < cutoff
        ]
        for scan_id in to_delete:
            del self._states[scan_id]
        return len(to_delete)

    def __len__(self) -> int:
        return len(self._states)
