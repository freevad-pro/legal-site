"""Общие type-aliases приложения.

В итерацию 3 переехал только `Status` — дальше сюда переберутся `Finding`/
`ScanResult` при появлении HTTP-API (итерация 4).
"""

from __future__ import annotations

from typing import Literal

Status = Literal["fail", "pass", "inconclusive"]
