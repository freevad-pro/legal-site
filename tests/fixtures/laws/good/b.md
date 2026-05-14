---
id: test-fz-b
title: "Тестовый закон B"
short_title: "test-B"
type: code
number: "2-B"

adopted_date: 2021-03-15
in_force_since: 2021-04-01
last_amended: 2023-09-15

status: in_force

official_sources:
  - title: "Источник B"
    url: https://example.com/test-b
  - title: "Дополнительный источник"
    url: https://example.com/test-b-2

applies_to:
  - ecommerce

related: [test-fz-a]
references_in_common: []

tags: [test, ecommerce]

verified_at: 2025-12-01
verified_by: test-fixture
verified: partial
verification_notes:
  - "Сумма штрафа уточняется"

violations:
  - id: test-b-violation
    article: "ст. 1"
    title: "Тестовое нарушение B"
    severity: low
    description: "Тестовое описание."
    detection:
      site_signals:
        - type: example_site_signal
          description: "Сигнал сайтового уровня"
          check: lookup_pages_by_keywords
          keywords:
            - "пример"
    penalties:
      - subject: citizen
        coap_article: "ст. 3 ч. 1"
        amount_min: 1000
        amount_max: 3000
        currency: RUB
    recommendation: "Исправьте."
    references: []
---

# Тестовый закон B
