// Шесть стилизованных React-«фрагментов сайта», показывающих типовое нарушение.
// Каждый — лёгкая визуализация без зависимости от реальных данных evidence.

export function FooterNoPolicy() {
  return (
    <div className="rounded-md border border-line bg-white p-4 text-xs">
      <div className="rounded bg-bg-soft p-3">
        <div className="flex items-center justify-between">
          <span className="font-semibold text-ink-primary">© example.ru</span>
          <span className="flex items-center gap-3 text-ink-secondary">
            <span>Контакты</span>
            <span>Доставка</span>
            <span className="text-ink-faint">Политика — не найдена</span>
          </span>
        </div>
      </div>
      <p className="mt-2 inline-block rounded bg-severity-critical-soft px-2 py-1 text-[11px] font-semibold text-severity-critical">
        Нет ссылки на политику обработки ПДн
      </p>
    </div>
  );
}

export function FormNoConsent() {
  return (
    <div className="rounded-md border border-line bg-white p-4 text-xs">
      <div className="flex flex-col gap-2 rounded bg-bg-soft p-3">
        <div className="h-7 rounded border border-line bg-white px-2 leading-7 text-ink-muted">
          Имя
        </div>
        <div className="h-7 rounded border border-line bg-white px-2 leading-7 text-ink-muted">
          you@example.ru
        </div>
        <button
          type="button"
          className="mt-1 inline-flex h-8 items-center justify-center rounded bg-brand px-3 text-[11px] font-semibold text-white"
        >
          Отправить
        </button>
      </div>
      <p className="mt-2 inline-block rounded bg-severity-critical-soft px-2 py-1 text-[11px] font-semibold text-severity-critical">
        Нет чекбокса согласия на обработку ПДн
      </p>
    </div>
  );
}

export function CookiesBeforeConsent() {
  return (
    <div className="rounded-md border border-line bg-white p-4 text-xs">
      <div className="rounded bg-bg-soft p-3">
        <div className="flex items-center justify-between">
          <span className="font-mono text-[11px] text-ink-secondary">
            Set-Cookie: _ym_uid=…
          </span>
          <span className="font-mono text-[11px] text-ink-secondary">
            Set-Cookie: ga=…
          </span>
        </div>
        <div className="mt-2 rounded border border-dashed border-line-strong bg-white p-2 text-ink-muted">
          Баннер согласия появится позже…
        </div>
      </div>
      <p className="mt-2 inline-block rounded bg-severity-high-soft px-2 py-1 text-[11px] font-semibold text-severity-high">
        Cookies устанавливаются до согласия
      </p>
    </div>
  );
}

export function ContactsNoRequisites() {
  return (
    <div className="rounded-md border border-line bg-white p-4 text-xs">
      <div className="rounded bg-bg-soft p-3">
        <p className="font-semibold text-ink-primary">Контакты</p>
        <p className="mt-2 text-ink-secondary">📧 hello@example.ru</p>
        <p className="text-ink-secondary">📞 +7 495 …</p>
        <p className="mt-2 text-ink-faint">ОГРН — не указан</p>
        <p className="text-ink-faint">ИНН — не указан</p>
      </div>
      <p className="mt-2 inline-block rounded bg-severity-critical-soft px-2 py-1 text-[11px] font-semibold text-severity-critical">
        Нет реквизитов продавца
      </p>
    </div>
  );
}

export function BannerNoMarking() {
  return (
    <div className="rounded-md border border-line bg-white p-4 text-xs">
      <div className="relative rounded bg-gradient-to-br from-link to-brand p-6 text-white">
        <p className="text-sm font-semibold">Магазин выгодных предложений</p>
        <p className="mt-1 text-xs opacity-90">Скидки до 50% — только сегодня</p>
        <span className="absolute right-2 top-2 rounded bg-white/20 px-2 py-0.5 text-[10px] font-mono">
          erid: —
        </span>
      </div>
      <p className="mt-2 inline-block rounded bg-severity-high-soft px-2 py-1 text-[11px] font-semibold text-severity-high">
        Рекламный креатив без маркировки ERID
      </p>
    </div>
  );
}

export function DntIgnored() {
  return (
    <div className="rounded-md border border-line bg-white p-4 text-xs">
      <div className="rounded bg-bg-soft p-3 font-mono text-[11px] leading-relaxed">
        <p>
          <span className="text-ink-secondary">→ Request</span>:{" "}
          <span className="text-ink-primary">DNT: 1</span>
        </p>
        <p className="mt-1">
          <span className="text-ink-secondary">← Set-Cookie</span>:{" "}
          <span className="text-severity-critical">_ym_uid=…</span>
        </p>
      </div>
      <p className="mt-2 inline-block rounded bg-severity-medium-soft px-2 py-1 text-[11px] font-semibold text-severity-medium">
        Заголовок DNT проигнорирован
      </p>
    </div>
  );
}
