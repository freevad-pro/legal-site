"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ProgressView } from "@/components/ProgressView";
import { ErrorView } from "@/components/ErrorView";
import { ResultView } from "@/components/ResultView";
import { getScan, ApiError } from "@/lib/api";
import type { ScanSummary } from "@/lib/types";

type Phase = "progress" | "result" | "error";

function ScanPageInner() {
  const router = useRouter();
  const params = useSearchParams();
  const scanId = params.get("id");
  const initialPhase = (params.get("phase") as Phase) ?? "progress";

  const [phase, setPhase] = useState<Phase>(initialPhase);
  const [summary, setSummary] = useState<ScanSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Подгружаем сводку при любой фазе — в progress нужен url для favicon/заголовка,
  // в result/error нужны with_llm, findings, error.
  useEffect(() => {
    if (!scanId) return;
    let cancelled = false;
    void (async () => {
      try {
        const data = await getScan(scanId);
        if (!cancelled) setSummary(data);
      } catch (err) {
        if (cancelled) return;
        const message =
          err instanceof ApiError ? err.detail : "Не удалось получить данные скана";
        setError(message);
        setPhase("error");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [scanId, phase]);

  const handleDone = useCallback(() => {
    setPhase("result");
    router.replace(`/scan?id=${scanId}&phase=result`, { scroll: true });
  }, [router, scanId]);

  const handleError = useCallback(
    (message: string | null) => {
      setError(message);
      setPhase("error");
    },
    [],
  );

  if (!scanId) {
    return <ErrorView message="Не указан идентификатор скана" />;
  }

  if (phase === "error") {
    return <ErrorView message={error} />;
  }

  if (phase === "progress") {
    // url берём из summary, как только он подгрузился; до этого показываем
    // нейтральный «—», чтобы не светить UUID.
    return (
      <ProgressView
        scanId={scanId}
        url={summary?.url ?? ""}
        onDone={handleDone}
        onError={handleError}
      />
    );
  }

  if (!summary) {
    return (
      <div className="container py-16 text-center text-ink-secondary">Загружаем отчёт…</div>
    );
  }
  return <ResultView summary={summary} />;
}

export default function ScanPage() {
  return (
    <Suspense fallback={null}>
      <ScanPageInner />
    </Suspense>
  );
}
