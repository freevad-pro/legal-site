"""Pydantic-модели справочника законов.

Соответствуют схеме [docs/laws/schema.md]. Все модели frozen и иммутабельны
в рантайме — корпус загружается один раз через [load_corpus] и дальше только читается.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, PrivateAttr, model_validator

LawType = Literal["federal_law", "code", "rf_law", "gov_decree", "order", "regulation"]
LawStatus = Literal["in_force", "repealed", "not_yet_in_force"]
VerifiedStatus = Literal["full", "partial", "unverified"]
Severity = Literal["low", "medium", "high", "critical"]
Subject = Literal["citizen", "official", "sole_proprietor", "small_org", "organization"]
AppliesTo = Literal[
    "all_websites", "ecommerce", "landing", "blog", "media", "service", "gov", "b2b"
]
LawCategory = Literal["privacy", "cookies", "advertising", "consumer", "info", "copyright"]
EvidenceTemplate = Literal[
    "footer_no_policy",
    "form_no_consent",
    "cookies_before_consent",
    "contacts_no_requisites",
    "banner_no_marking",
    "dnt_ignored",
]

_VIOLATION_ID_RE = re.compile(r"^[a-z0-9-]+$")


class Source(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    title: str
    url: HttpUrl


class Penalty(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    subject: Subject
    coap_article: str
    amount_min: int | None = None
    amount_max: int | None = None
    currency: Literal["RUB"] = "RUB"
    notes: str | None = None

    @model_validator(mode="after")
    def _amounts_ordered(self) -> Penalty:
        if (
            self.amount_min is not None
            and self.amount_max is not None
            and self.amount_max < self.amount_min
        ):
            raise ValueError(f"amount_max ({self.amount_max}) < amount_min ({self.amount_min})")
        return self


class PageSignal(BaseModel):
    """Сигнал страничного уровня. Доп. поля разрешены — разные типы сигналов
    используют разные опции (expected_status, min_chars, source, combine, …).
    Доступ к ним — через `signal.model_extra`."""

    model_config = ConfigDict(frozen=True, extra="allow")

    type: str
    description: str
    check: str | None = None
    html_patterns: tuple[str, ...] = ()
    required_absent: tuple[str, ...] = ()
    required_keywords: tuple[str, ...] = ()
    required_headers: tuple[str, ...] = ()
    required_protocol: str | None = None


class SiteSignal(BaseModel):
    """Сигнал сайтового уровня. Аналогично PageSignal — extra='allow'."""

    model_config = ConfigDict(frozen=True, extra="allow")

    type: str
    description: str
    check: str | None = None
    required_keywords: tuple[str, ...] = ()


class Detection(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    page_signals: tuple[PageSignal, ...] = ()
    site_signals: tuple[SiteSignal, ...] = ()

    @model_validator(mode="after")
    def _at_least_one_signal(self) -> Detection:
        if not self.page_signals and not self.site_signals:
            raise ValueError(
                "detection: at least one of page_signals/site_signals must be non-empty"
            )
        return self


class Violation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: Annotated[str, Field(pattern=_VIOLATION_ID_RE.pattern)]
    article: str
    title: str
    severity: Severity
    description: str
    detection: Detection
    penalties: tuple[Penalty, ...] = ()
    recommendation: str
    references: tuple[str, ...] = ()
    evidence_template: EvidenceTemplate | None = None


class ReviewLogEntry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    date: date
    by: str
    findings: str


class Law(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    title: str
    short_title: str
    type: LawType
    number: str

    adopted_date: date
    in_force_since: date
    last_amended: date

    status: LawStatus

    category: LawCategory
    icon: Annotated[str, Field(pattern=r"^[a-z][a-z0-9-]*$")]
    short_description: Annotated[str, Field(min_length=1, max_length=60)]

    official_sources: tuple[Source, ...]
    regulators: tuple[str, ...] = ()
    applies_to: tuple[AppliesTo, ...]
    related: tuple[str, ...] = ()
    references_in_common: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()

    verified_at: date
    verified_by: str
    verified: VerifiedStatus
    verification_notes: tuple[str, ...] = ()
    review_log: tuple[ReviewLogEntry, ...] = ()

    violations: tuple[Violation, ...]

    @model_validator(mode="after")
    def _check_consistency(self) -> Law:
        if not self.official_sources:
            raise ValueError(f"{self.id}: official_sources must have at least one entry")
        if not self.violations:
            raise ValueError(f"{self.id}: violations must not be empty")
        if "all_websites" in self.applies_to and len(self.applies_to) > 1:
            raise ValueError(
                f"{self.id}: applies_to=all_websites is mutually exclusive with other categories"
            )
        if self.verified == "partial" and not self.verification_notes:
            raise ValueError(f"{self.id}: verified=partial requires non-empty verification_notes")
        return self


class CorpusBundle(BaseModel):
    """Иммутабельная коллекция всех загруженных законов корпуса.

    Индексы по `laws_by_id` и `violations_by_id` строятся один раз в валидаторе
    и доступны как PrivateAttr (не входят в model_dump). `common_ids` —
    идентификаторы документов из `docs/laws/common/`, нужны для резолва
    `references_in_common`.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    laws: tuple[Law, ...]
    common_ids: frozenset[str] = frozenset()

    _laws_by_id: dict[str, Law] = PrivateAttr(default_factory=dict)
    _violations_by_id: dict[str, tuple[str, Violation]] = PrivateAttr(default_factory=dict)

    @model_validator(mode="after")
    def _build_indexes_and_validate(self) -> CorpusBundle:
        laws_by_id: dict[str, Law] = {}
        for law in self.laws:
            if law.id in laws_by_id:
                raise ValueError(f"duplicate law id: {law.id}")
            laws_by_id[law.id] = law

        violations_by_id: dict[str, tuple[str, Violation]] = {}
        for law in self.laws:
            for violation in law.violations:
                if violation.id in violations_by_id:
                    prev_law_id, _ = violations_by_id[violation.id]
                    raise ValueError(
                        f"duplicate violation id: {violation.id} in {prev_law_id} and {law.id}"
                    )
                violations_by_id[violation.id] = (law.id, violation)

        for law in self.laws:
            for related_id in law.related:
                if related_id not in laws_by_id:
                    raise ValueError(
                        f"{law.id}: related id {related_id!r} does not exist in corpus"
                    )
            for common_id in law.references_in_common:
                if common_id not in self.common_ids:
                    raise ValueError(
                        f"{law.id}: references_in_common id {common_id!r} not found in common/"
                    )

        object.__setattr__(self, "_laws_by_id", laws_by_id)
        object.__setattr__(self, "_violations_by_id", violations_by_id)
        return self

    @property
    def total_violations(self) -> int:
        return len(self._violations_by_id)

    def find_law(self, law_id: str) -> Law | None:
        return self._laws_by_id.get(law_id)

    def find_violation(self, violation_id: str) -> tuple[str, Violation] | None:
        return self._violations_by_id.get(violation_id)

    def all_violations(self) -> tuple[tuple[str, Violation], ...]:
        return tuple(self._violations_by_id.values())
