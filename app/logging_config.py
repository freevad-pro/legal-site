"""Логирование с контекстом скана.

`scan_id_var` — `ContextVar`, который воркер заполняет в начале работы,
форматтер достаёт его в каждую запись лога. `docker logs ... | grep scan=<uuid>`
даёт трассировку одного скана.
"""

from __future__ import annotations

import logging
from contextvars import ContextVar

scan_id_var: ContextVar[str | None] = ContextVar("scan_id", default=None)


class ScanIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.scan_id = scan_id_var.get() or "-"
        return True


def setup_logging(level: str) -> None:
    """Сбросить корневой логгер и поднять единственный handler с фильтром."""

    handler = logging.StreamHandler()
    handler.addFilter(ScanIdFilter())
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s [scan=%(scan_id)s] %(name)s: %(message)s"
        )
    )
    root = logging.getLogger()
    root.setLevel(level)
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)
