---
id: test-dup-x
title: "Тестовый закон X с дублирующим violation id"
short_title: "test-X"
type: federal_law
number: "X"

adopted_date: 2020-01-01
in_force_since: 2020-02-01
last_amended: 2024-06-01

status: in_force

official_sources:
  - title: "Источник"
    url: https://example.com/x

applies_to:
  - all_websites

verified_at: 2025-12-01
verified_by: test-fixture
verified: full

violations:
  - id: shared-violation-id
    article: "ст. 1"
    title: "Нарушение X"
    severity: low
    description: "Текст."
    detection:
      page_signals:
        - type: x_signal
          description: "test"
          html_patterns: ['div']
    penalties:
      - subject: organization
        coap_article: "ст. 1"
        amount_min: 1000
        amount_max: 2000
        currency: RUB
    recommendation: "Fix."
    references: []
---
