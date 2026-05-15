"""Общие type-aliases приложения.

В итерацию 3 переехал только `Status` — дальше сюда переберутся `Finding`/
`ScanResult` при появлении HTTP-API (итерация 4).
"""

from __future__ import annotations

from typing import Literal

Status = Literal["fail", "pass", "inconclusive"]

# Причина статуса `inconclusive` для finding'а. См. ADR-0003.
#
# - `check_not_implemented` — check-функция не реализована в текущей итерации
#   (заглушка `_not_implemented`, ветка `combine`, неизвестное имя check).
#   Engine скрывает такие findings из отчёта.
# - `context_dependent` — детерминированно решить невозможно, требуется LLM
#   (зарезервировано под итерацию 7).
# - `evidence_missing` — страница не отдала нужного артефакта (нет PD-формы,
#   нет URL политики и т. п.) — реальный inconclusive, не stub.
InconclusiveReason = Literal["check_not_implemented", "context_dependent", "evidence_missing"]
