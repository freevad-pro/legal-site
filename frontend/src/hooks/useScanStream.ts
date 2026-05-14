"use client";

import { useEffect, useRef, useState } from "react";
import { eventsUrl } from "@/lib/api";
import { LAWS } from "@/data/laws.generated";
import type { LawCategory, Severity, SseDonePayload, SseViolationPayload } from "@/lib/types";

type StreamStatus = "connecting" | "streaming" | "done" | "error";

type SeverityCounts = Record<Severity, number>;

interface CategoryProgress {
  category: LawCategory;
  seen: number; // уникальные violation_id из этой категории
  total: number; // ожидаемое число из bundled JSON
  failed: number;
}

interface StreamState {
  status: StreamStatus;
  errorMessage: string | null;
  severity: SeverityCounts;
  totalProcessed: number;
  lastViolationId: string | null;
  flash: { id: number; title: string } | null;
  categories: CategoryProgress[];
}

const ZERO_SEVERITY: SeverityCounts = { critical: 0, high: 0, medium: 0, low: 0 };

const LAW_TO_CATEGORY: Record<string, LawCategory> = Object.fromEntries(
  LAWS.map((law) => [law.id, law.category]),
);

const CATEGORY_ORDER: readonly LawCategory[] = [
  "privacy",
  "advertising",
  "consumer",
  "info",
  "copyright",
];

function buildInitialCategories(): CategoryProgress[] {
  const totals = new Map<LawCategory, number>();
  for (const law of LAWS) {
    totals.set(law.category, (totals.get(law.category) ?? 0) + law.violationsCount);
  }
  return CATEGORY_ORDER.filter((c) => totals.has(c)).map((category) => ({
    category,
    seen: 0,
    total: totals.get(category) ?? 0,
    failed: 0,
  }));
}

const INITIAL_STATE: StreamState = {
  status: "connecting",
  errorMessage: null,
  severity: { ...ZERO_SEVERITY },
  totalProcessed: 0,
  lastViolationId: null,
  flash: null,
  categories: buildInitialCategories(),
};

export function useScanStream(scanId: string | null): StreamState {
  const [state, setState] = useState<StreamState>(INITIAL_STATE);
  const seenViolationsRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    if (!scanId) return;
    seenViolationsRef.current = new Set();
    setState({ ...INITIAL_STATE, categories: buildInitialCategories() });

    const url = eventsUrl(scanId);
    const source = new EventSource(url, { withCredentials: true });

    source.addEventListener("scanner_started", () => {
      setState((prev) => ({ ...prev, status: "streaming" }));
    });

    source.addEventListener("scanner_done", () => {
      setState((prev) => ({ ...prev, status: "streaming" }));
    });

    source.addEventListener("violation_evaluated", (event) => {
      let payload: { timestamp: string; payload: SseViolationPayload };
      try {
        payload = JSON.parse((event as MessageEvent<string>).data);
      } catch {
        return;
      }
      const { violation_id, law_id, title, status, severity } = payload.payload;
      if (seenViolationsRef.current.has(violation_id)) return;
      seenViolationsRef.current.add(violation_id);

      const category = LAW_TO_CATEGORY[law_id];

      setState((prev) => {
        const nextSeverity = { ...prev.severity };
        if (status === "fail") {
          nextSeverity[severity] = (nextSeverity[severity] ?? 0) + 1;
        }

        const nextCategories = prev.categories.map((c) =>
          c.category === category
            ? {
                ...c,
                seen: c.seen + 1,
                failed: status === "fail" ? c.failed + 1 : c.failed,
              }
            : c,
        );

        return {
          ...prev,
          severity: nextSeverity,
          totalProcessed: prev.totalProcessed + 1,
          lastViolationId: violation_id,
          flash: status === "fail" ? { id: Date.now(), title } : prev.flash,
          categories: nextCategories,
        };
      });
    });

    source.addEventListener("done", (event) => {
      let payload: { timestamp: string; payload: SseDonePayload } | null = null;
      try {
        payload = JSON.parse((event as MessageEvent<string>).data);
      } catch {
        // empty
      }
      setState((prev) => ({
        ...prev,
        status: "done",
        errorMessage: payload?.payload.error ?? null,
      }));
      source.close();
    });

    source.addEventListener("error", (event) => {
      // event может быть как явный SSE-event «error» (типизированный, с data),
      // так и системная ошибка соединения (data отсутствует).
      const data = (event as MessageEvent<string | undefined>).data;
      if (data) {
        try {
          const parsed = JSON.parse(data) as { payload?: { message?: string } };
          setState((prev) => ({
            ...prev,
            status: "error",
            errorMessage: parsed?.payload?.message ?? "Скан завершился ошибкой",
          }));
          source.close();
          return;
        } catch {
          // fallthrough to network-error branch
        }
      }
      // Сетевой обрыв — EventSource сам переподключится; не считаем терминальным.
      // Но если соединение перешло в CLOSED — это финал.
      if (source.readyState === EventSource.CLOSED) {
        setState((prev) =>
          prev.status === "done" ? prev : { ...prev, status: "error", errorMessage: "Соединение прервано" },
        );
      }
    });

    return () => {
      source.close();
    };
  }, [scanId]);

  return state;
}
