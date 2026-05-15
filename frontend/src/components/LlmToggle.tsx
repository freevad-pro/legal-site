"use client";

import { cn } from "@/lib/utils";

interface Props {
  authenticated: boolean;
  enabled: boolean;
  onChange: (next: boolean) => void;
}

// Тоггл живёт внутри зелёной CTA-карточки — оформляется белым inline,
// без отдельной кнопки «Войти» (она уже в шапке).
export function LlmToggle({ authenticated, enabled, onChange }: Props) {
  if (!authenticated) {
    return (
      <p className="text-sm text-white/85">
        Расширенный анализ — доступен после входа в аккаунт.
      </p>
    );
  }

  return (
    <label className="inline-flex cursor-pointer items-center gap-3 text-sm text-white/95">
      <button
        type="button"
        role="switch"
        aria-checked={enabled}
        onClick={() => onChange(!enabled)}
        className={cn(
          "relative inline-flex h-6 w-11 shrink-0 rounded-full border-2 border-transparent transition-colors",
          enabled ? "bg-white" : "bg-white/30",
        )}
      >
        <span
          className={cn(
            "pointer-events-none inline-block h-5 w-5 transform rounded-full shadow ring-0 transition",
            enabled ? "translate-x-5 bg-brand" : "translate-x-0 bg-white",
          )}
        />
      </button>
      <span>Расширенный анализ</span>
    </label>
  );
}
