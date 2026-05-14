"use client";

import Link from "next/link";
import { AlertTriangle, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";

interface Props {
  message: string | null;
  onRetry?: () => void;
}

export function ErrorView({ message, onRetry }: Props) {
  return (
    <div className="container py-16">
      <div className="mx-auto flex max-w-[560px] flex-col items-center gap-4 rounded-card border border-severity-critical-border bg-severity-critical-soft p-8 text-center">
        <AlertTriangle className="h-10 w-10 text-severity-critical" />
        <h1 className="text-2xl font-bold text-severity-critical">Не удалось проверить сайт</h1>
        <p className="text-sm text-ink-secondary">
          {message ??
            "Сайт не ответил, либо проверка завершилась с ошибкой. Попробуйте ещё раз позже."}
        </p>
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
