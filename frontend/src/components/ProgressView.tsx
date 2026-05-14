"use client";

import { useEffect } from "react";
import { Check, Loader2, Circle } from "lucide-react";
import { DomainFavicon } from "@/components/DomainFavicon";
import { useScanStream } from "@/hooks/useScanStream";
import { hostFromUrl } from "@/lib/favicon";
import { cn } from "@/lib/utils";
import type { LawCategory } from "@/lib/types";

const CATEGORY_TITLES: Record<LawCategory, string> = {
  privacy: "Персональные данные",
  cookies: "Cookies",
  advertising: "Реклама и маркировка",
  consumer: "Защита потребителей",
  info: "Информация и контент",
  copyright: "Интеллектуальная собственность",
};

interface Props {
  scanId: string;
  url: string;
  onDone: () => void;
  onError: (message: string | null) => void;
}

export function ProgressView({ scanId, url, onDone, onError }: Props) {
  const state = useScanStream(scanId);
  const host = hostFromUrl(url);

  useEffect(() => {
    if (state.status === "done") onDone();
    else if (state.status === "error") onError(state.errorMessage);
  }, [state.status, state.errorMessage, onDone, onError]);

  const totalExpected = state.categories.reduce((s, c) => s + c.total, 0);
  const processed = state.totalProcessed;
  const percent = totalExpected
    ? Math.min(100, Math.round((processed / totalExpected) * 100))
    : 0;

  const currentCategory =
    state.categories.find((c) => c.seen > 0 && c.seen < c.total) ??
    state.categories.find((c) => c.seen === 0) ??
    state.categories[state.categories.length - 1];

  return (
    <div className="container py-12">
      <div className="rounded-card border border-line bg-white p-8">
        <div className="flex items-center gap-3">
          <span className="relative inline-flex h-3 w-3">
            <span className="absolute inline-flex h-full w-full animate-pulse-dot rounded-full bg-brand opacity-70" />
            <span className="relative inline-flex h-3 w-3 rounded-full bg-brand" />
          </span>
          <DomainFavicon host={host} size="sm" />
          <span className="font-mono text-sm text-ink-secondary">{host}</span>
        </div>

        <h1 className="mt-6 text-2xl font-bold sm:text-[28px]">
          {currentCategory
            ? `Проверяем: ${CATEGORY_TITLES[currentCategory.category]}`
            : "Подготовка к проверке…"}
        </h1>

        <div className="mt-8 h-2 w-full overflow-hidden rounded-full bg-bg-soft">
          <div
            className="h-full bg-brand progress-stripes animate-progress-stripe transition-[width] duration-300"
            style={{ width: `${percent}%` }}
            aria-label={`Прогресс ${percent}%`}
          />
        </div>
        <p className="mt-2 text-xs font-mono text-ink-secondary">
          {processed} / {totalExpected} проверок · {percent}%
        </p>

        {state.flash ? (
          <p
            key={state.flash.id}
            className="mt-4 inline-flex items-center gap-2 text-sm text-ink-secondary animate-flash-in"
          >
            <span className="text-severity-high">+</span>
            <span>Только что: {state.flash.title}</span>
          </p>
        ) : null}

        <div className="mt-8 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <SeverityTile label="Критический" value={state.severity.critical} tone="critical" />
          <SeverityTile label="Высокий" value={state.severity.high} tone="high" />
          <SeverityTile label="Средний" value={state.severity.medium} tone="medium" />
          <SeverityTile label="Низкий" value={state.severity.low} tone="low" />
        </div>

        <ul className="mt-8 flex flex-col gap-2">
          {state.categories.map((c) => {
            const isDone = c.total > 0 && c.seen >= c.total;
            const isCurrent = !isDone && c === currentCategory;
            const Icon = isDone ? Check : isCurrent ? Loader2 : Circle;
            return (
              <li
                key={c.category}
                className={cn(
                  "flex items-center justify-between rounded-md px-3 py-2 text-sm",
                  isCurrent && "bg-bg-soft",
                )}
              >
                <span className="flex items-center gap-3">
                  <Icon
                    className={cn(
                      "h-4 w-4",
                      isDone && "text-brand",
                      isCurrent && "text-ink-primary animate-spin",
                      !isDone && !isCurrent && "text-ink-faint",
                    )}
                  />
                  <span
                    className={cn(
                      "font-medium",
                      isDone ? "text-ink-secondary" : "text-ink-primary",
                    )}
                  >
                    {CATEGORY_TITLES[c.category]}
                  </span>
                </span>
                <span className="font-mono text-xs text-ink-secondary">
                  {c.seen} / {c.total}
                </span>
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
}

function SeverityTile({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: "critical" | "high" | "medium" | "low";
}) {
  const colorClass = {
    critical: "text-severity-critical",
    high: "text-severity-high",
    medium: "text-severity-medium",
    low: "text-severity-low",
  }[tone];

  return (
    <div className="rounded-card bg-bg-soft p-4">
      <p className={cn("font-mono text-[32px] font-bold tabular-nums", colorClass)}>{value}</p>
      <p className="text-xs text-ink-secondary">{label}</p>
    </div>
  );
}
