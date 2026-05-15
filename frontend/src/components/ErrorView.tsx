"use client";

import Link from "next/link";
import { AlertTriangle, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { humanizeScanError } from "@/lib/scan-error";

interface Props {
  message: string | null;
  onRetry?: () => void;
}

export function ErrorView({ message, onRetry }: Props) {
  const { title, description, details } = humanizeScanError(message);

  return (
    <div className="container py-16">
      <div className="mx-auto flex max-w-[560px] flex-col items-center gap-4 rounded-card border border-severity-critical-border bg-severity-critical-soft p-8 text-center">
        <AlertTriangle className="h-10 w-10 text-severity-critical" />
        <h1 className="text-2xl font-bold text-severity-critical">{title}</h1>
        {description ? <p className="text-sm text-ink-secondary">{description}</p> : null}

        {details ? (
          <details className="w-full text-left">
            <summary className="cursor-pointer text-xs text-ink-muted hover:text-ink-secondary">
              Технические детали
            </summary>
            <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap break-words rounded-md bg-white/60 p-3 text-left font-mono text-[11px] leading-snug text-ink-secondary">
              {details}
            </pre>
          </details>
        ) : null}

        <div className="mt-2 flex flex-wrap items-center justify-center gap-3">
          {onRetry ? (
            <Button onClick={onRetry} variant="primary">
              <RotateCcw className="h-4 w-4" />
              <span>Попробовать снова</span>
            </Button>
          ) : null}
          <Link href="/">
            <Button variant="outline">На главную</Button>
          </Link>
        </div>
      </div>
    </div>
  );
}
