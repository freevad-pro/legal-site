"use client";

import Link from "next/link";
import { cn } from "@/lib/utils";

interface Props {
  authenticated: boolean;
  enabled: boolean;
  onChange: (next: boolean) => void;
}

export function LlmToggle({ authenticated, enabled, onChange }: Props) {
  const disabled = !authenticated;

  return (
    <div
      className={cn(
        "flex items-center justify-between gap-3 rounded-card border border-line bg-white px-4 py-3",
        disabled && "bg-bg-soft",
      )}
    >
      <div className="flex flex-col">
        <span className="text-sm font-semibold text-ink-primary">
          Расширенный анализ
        </span>
        <span className="text-xs text-ink-secondary">
          {disabled
            ? "Доступен после входа в аккаунт."
            : "Подключает семантические проверки текстов на сайте."}
        </span>
      </div>

      {disabled ? (
        <Link
          href="/login"
          className="text-sm font-medium text-link hover:underline"
        >
          Войти
        </Link>
      ) : (
        <button
          type="button"
          role="switch"
          aria-checked={enabled}
          onClick={() => onChange(!enabled)}
          className={cn(
            "relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors",
            enabled ? "bg-brand" : "bg-ink-faint",
          )}
        >
          <span
            className={cn(
              "pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition",
              enabled ? "translate-x-5" : "translate-x-0",
            )}
          />
        </button>
      )}
    </div>
  );
}
