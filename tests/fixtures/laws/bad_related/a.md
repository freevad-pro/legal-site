---
id: test-bad-related
title: "Закон со ссылкой на несуществующий related id"
short_title: "test-BR"
type: federal_law
number: "BR"

adopted_date: 2020-01-01
in_force_since: 2020-02-01
last_amended: 2024-06-01

status: in_force

official_sources:
  - title: "Источник"
    url: https://example.com/br

applies_to:
  - all_websites

related: [non-existent-law]

verified_at: 2025-12-01
verified_by: test-fixture
verified: full

violations:
  - id: test-bad-related-violation
    article: "ст. 1"
    title: "Нарушение"
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
