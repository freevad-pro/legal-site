"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { FileDown, Info, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { DomainFavicon } from "@/components/DomainFavicon";
import { FindingCard } from "@/components/FindingCard";
import { auditNumber, hostFromUrl } from "@/lib/favicon";
import { reportPdfUrl } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { Finding, ScanSummary, Severity } from "@/lib/types";

const SEVERITY_ORDER: Severity[] = ["critical", "high", "medium", "low"];

const SEVERITY_LABEL: Record<Severity, string> = {
  critical: "Критический",
  high: "Высокий",
  medium: "Средний",
  low: "Низкий",
};

const SEVERITY_COLOR: Record<Severity, string> = {
  critical: "text-severity-critical",
  high: "text-severity-high",
  medium: "text-severity-medium",
  low: "text-severity-low",
};

function countBySeverity(findings: readonly Finding[]) {
  const counts: Record<Severity, number> = { critical: 0, high: 0, medium: 0, low: 0 };
  for (const f of findings) {
    if (f.status === "fail") {
      counts[f.severity] = (counts[f.severity] ?? 0) + 1;
    }
  }
  return counts;
}

export function ResultView({ summary }: { summary: ScanSummary }) {
  const host = hostFromUrl(summary.url);
  const result = summary.result;
  // Стабильная ссылка на массив, иначе useMemo ниже пересчитывался бы каждый рендер.
  const findings = useMemo(() => result?.findings ?? [], [result]);

  const failedFindings = useMemo(() => findings.filter((f) => f.status === "fail"), [findings]);
  const inconclusiveFindings = useMemo(
    () => findings.filter((f) => f.status === "inconclusive"),
    [findings],
  );
  const counts = useMemo(() => countBySeverity(findings), [findings]);
  const sortedFailed = useMemo(() => {
    const order: Record<Severity, number> = { critical: 0, high: 1, medium: 2, low: 3 };
    return [...failedFindings].sort((a, b) => order[a.severity] - order[b.severity]);
  }, [failedFindings]);

  const allCards = useMemo(
    () => [...sortedFailed, ...inconclusiveFindings],
    [sortedFailed, inconclusiveFindings],
  );

  // По DoD: «все карточки раскрыты по умолчанию». Перестраиваем словарь, когда
  // findings меняются (например, после первой загрузки summary).
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  useEffect(() => {
    setExpanded(Object.fromEntries(allCards.map((f) => [f.violation_id, true])));
  }, [allCards]);

  const allExpanded = allCards.length > 0 && allCards.every((f) => expanded[f.violation_id]);

  function toggle(id: string) {
    setExpanded((prev) => ({ ...prev, [id]: !prev[id] }));
  }

  function setAll(value: boolean) {
    setExpanded(Object.fromEntries(allCards.map((f) => [f.violation_id, value])));
  }

  const number = auditNumber(summary.scan_id, summary.started_at);

  return (
    <>
      <div className="sticky top-16 z-30 border-b border-line bg-white/94 backdrop-blur supports-[backdrop-filter]:bg-white/80">
        <div className="container flex h-16 items-center justify-between gap-4">
          <div className="flex items-center gap-3 min-w-0">
            <DomainFavicon host={host} size="md" />
            <div className="flex flex-col min-w-0">
              <span className="font-mono text-sm font-semibold text-ink-primary truncate">
                {host}
              </span>
              <span className="font-mono text-[11px] text-ink-secondary">№ {number}</span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Link href="/">
              <Button variant="outline" size="sm">
                <RotateCcw className="h-4 w-4" />
                <span className="hidden sm:inline">Новая</span>
              </Button>
            </Link>
            <a href={reportPdfUrl(summary.scan_id)} download>
              <Button size="sm">
                <FileDown className="h-4 w-4" />
                <span>PDF</span>
              </Button>
            </a>
          </div>
        </div>
      </div>

      <div className="container flex flex-col gap-8 py-12">
        <aside className="flex items-start gap-3 rounded-md bg-bg-soft p-4 text-sm text-ink-secondary">
          <Info className="mt-0.5 h-4 w-4 text-link" />
          <p>
            <strong className="text-ink-primary">Ограничение ответственности.</strong> Отчёт —
            техническая оценка по корпусу. Окончательная квалификация и применение санкций
            остаются за регулятором и судом.
          </p>
        </aside>

        <section className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {SEVERITY_ORDER.map((s) => (
            <div key={s} className="rounded-card bg-bg-soft p-4">
              <p
                className={cn(
                  "font-mono text-[32px] font-bold tabular-nums",
                  SEVERITY_COLOR[s],
                )}
              >
                {counts[s]}
              </p>
              <p className="text-xs text-ink-secondary">{SEVERITY_LABEL[s]}</p>
            </div>
          ))}
        </section>

        {!summary.with_llm ? (
          <section className="rounded-card border border-brand/30 bg-brand-soft p-5 text-sm text-ink-primary">
            <p className="font-semibold">Расширенный анализ доступен после входа</p>
            <p className="mt-1 text-ink-secondary">
              Семантические проверки текстов (политика, согласия, тексты cookie-баннеров) и
              распознавание неочевидных нарушений добавляются по флагу «Расширенный анализ» — для
              этого нужна авторизация.
            </p>
            <div className="mt-3 flex flex-wrap gap-3">
              <Link href="/login">
                <Button variant="primary" size="sm">
                  Войти
                </Button>
              </Link>
            </div>
          </section>
        ) : null}

        <section>
          <div className="mb-4 flex items-center justify-between">
            <p className="text-sm text-ink-secondary">
              Нарушений: <strong className="text-ink-primary">{sortedFailed.length}</strong>
            </p>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setAll(!allExpanded)}
              aria-label={allExpanded ? "Свернуть все" : "Раскрыть все"}
            >
              {allExpanded ? "Свернуть все" : "Раскрыть все"}
            </Button>
          </div>

          {sortedFailed.length === 0 ? (
            <div className="rounded-card border border-brand/30 bg-brand-soft p-6 text-center">
              <p className="text-base font-semibold text-brand-dark">Нарушений не найдено</p>
              <p className="mt-2 text-sm text-ink-secondary">
                Детерминированные проверки не обнаружили проблем. Это не гарантирует полного
                соответствия — часть формальных проверок ловит только грубые нарушения.
              </p>
            </div>
          ) : (
            <div className="flex flex-col gap-3">
              {sortedFailed.map((f) => (
                <FindingCard
                  key={f.violation_id}
                  finding={f}
                  expanded={Boolean(expanded[f.violation_id])}
                  onToggle={() => toggle(f.violation_id)}
                />
              ))}
            </div>
          )}
        </section>

        {inconclusiveFindings.length > 0 ? (
          <section>
            <div className="mb-4 flex flex-col gap-1">
              <span className="eyebrow">Требуют ручной проверки</span>
              <h2 className="text-2xl font-bold">
                {inconclusiveFindings.length} пунктов, которые не удалось проверить автоматически
              </h2>
            </div>
            <div className="flex flex-col gap-3">
              {inconclusiveFindings.map((f) => (
                <FindingCard
                  key={f.violation_id}
                  finding={f}
                  expanded={Boolean(expanded[f.violation_id])}
                  onToggle={() => toggle(f.violation_id)}
                />
              ))}
            </div>
          </section>
        ) : null}

        <section className="rounded-card bg-brand p-8 text-center text-white">
          <h2 className="text-2xl font-bold">Готово. Сохраните отчёт</h2>
          <p className="mt-2 text-white/90">
            PDF можно скачать одним кликом и поделиться с разработчиком, юристом, маркетологом.
          </p>
          <div className="mt-5 flex flex-wrap items-center justify-center gap-3">
            <a href={reportPdfUrl(summary.scan_id)} download>
              <Button variant="dark">
                <FileDown className="h-4 w-4" />
                <span>Скачать PDF</span>
              </Button>
            </a>
            <Link href="/">
              <Button variant="outline" className="bg-transparent text-white border-white/40 hover:bg-white/10">
                Проверить другой
              </Button>
            </Link>
          </div>
        </section>
      </div>
    </>
  );
}
