---
id: test-fz-a
title: "Тестовый закон A для проверки loader'а"
short_title: "test-A"
type: federal_law
number: "1-A"

adopted_date: 2020-01-01
in_force_since: 2020-02-01
last_amended: 2024-06-01

status: in_force

category: privacy
icon: lock
short_description: "Тестовый закон A"

official_sources:
  - title: "Тестовый источник"
    url: https://example.com/test-a

regulators:
  - Тест-регулятор

applies_to:
  - all_websites

related: []
references_in_common: [test-common-x]

tags: [test, sample]

verified_at: 2025-12-01
verified_by: test-fixture
verified: full

violations:
  - id: test-a-violation-html-patterns
    article: "ст. 1"
    title: "Нарушение через html_patterns"
    severity: high
    description: |
      Тестовое нарушение, ловится через CSS-селектор.
    detection:
      page_signals:
        - type: form_without_consent_checkbox
          description: "Форма без чекбокса"
          html_patterns:
            - 'input[type="email"]'
          required_absent:
            - 'input[type="checkbox"][name*="consent" i]'
    penalties:
      - subject: organization
        coap_article: "ст. 1 ч. 1"
        amount_min: 10000
        amount_max: 50000
        currency: RUB
    recommendation: "Добавьте чекбокс согласия."
    references: []

  - id: test-a-violation-keywords
    article: "ст. 2"
    title: "Нарушение через required_keywords"
    severity: medium
    description: |
      Тестовое нарушение, ловится через ключевые слова.
    detection:
      page_signals:
        - type: missing_required_keywords
          description: "Нет ключевых разделов"
          required_keywords:
            - "согласие"
            - "обработка"
    penalties:
      - subject: organization
        coap_article: "ст. 2 ч. 1"
        amount_min: 5000
        amount_max: 20000
        currency: RUB
    recommendation: "Добавьте раздел про обработку."
    references: []
---

# Тестовый закон A

Содержимое для людей.
