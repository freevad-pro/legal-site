"use client";

import { useEffect } from "react";
import { AlertTriangle, X } from "lucide-react";
import { Button } from "@/components/ui/button";

interface Props {
  open: boolean;
  kind: "missing-deps" | "generic";
  detail: string | null;
  onClose: () => void;
}

// Простой модальный диалог. Не используем @radix-ui/react-dialog,
// чтобы не тянуть зависимость ради единственной модалки.
export function PdfErrorDialog({ open, kind, detail, onClose }: Props) {
  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
    >
      <div
        className="relative w-full max-w-lg rounded-card bg-white p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          type="button"
          onClick={onClose}
          className="absolute right-4 top-4 rounded-md p-1 text-ink-secondary hover:bg-bg-soft hover:text-ink-primary"
          aria-label="Закрыть"
        >
          <X className="h-4 w-4" />
        </button>

        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-severity-critical-soft">
            <AlertTriangle className="h-5 w-5 text-severity-critical" />
          </div>
          <div className="flex flex-col gap-1">
            <h2 className="text-lg font-bold text-ink-primary">
              {kind === "missing-deps"
                ? "PDF недоступен на этом окружении"
                : "Не удалось сформировать PDF"}
            </h2>
            {kind === "missing-deps" ? (
              <p className="text-sm text-ink-secondary">
                Рендер PDF использует WeasyPrint, которому нужны системные библиотеки{" "}
                <strong className="text-ink-primary">GTK / Pango / Cairo</strong>. В вашем окружении
                их нет — обычно это локальный запуск на Windows без установленного GTK runtime.
              </p>
            ) : (
              <p className="text-sm text-ink-secondary">
                Сервер вернул ошибку при сборке отчёта.
              </p>
            )}
          </div>
        </div>

        {kind === "missing-deps" ? (
          <div className="mt-6 flex flex-col gap-4 text-sm">
            <section className="rounded-md border border-line bg-bg-soft p-4">
              <h3 className="font-semibold text-ink-primary">Локально на Windows</h3>
              <ol className="mt-2 list-decimal space-y-1 pl-5 text-ink-secondary">
                <li>
                  Скачать установщик GTK 3 Runtime:{" "}
                  <a
                    href="https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases/latest"
                    target="_blank"
                    rel="noreferrer"
                    className="text-link underline"
                  >
                    GitHub releases
                  </a>{" "}
                  (~30&nbsp;МБ).
                </li>
                <li>
                  Установить. При установке отметить опцию «Set up PATH environment variable to
                  include GTK+».
                </li>
                <li>
                  Перезапустить терминал и `make dev` — кнопка PDF заработает.
                </li>
              </ol>
            </section>

            <section className="rounded-md border border-brand/30 bg-brand-soft p-4">
              <h3 className="font-semibold text-ink-primary">На сервере (Linux / Docker)</h3>
              <p className="mt-2 text-ink-secondary">
                Зависимости ставятся одной строкой и обычно уже стоят в production-окружении:
              </p>
              <pre className="mt-2 overflow-x-auto rounded bg-white p-3 font-mono text-[12px] text-ink-primary">
                apt-get install -y libpango-1.0-0 libpangoft2-1.0-0
              </pre>
              <p className="mt-2 text-ink-secondary">
                После этого PDF работает «из коробки» — без действий со стороны пользователя.
              </p>
            </section>
          </div>
        ) : null}

        {detail ? (
          <details className="mt-4">
            <summary className="cursor-pointer text-xs text-ink-muted hover:text-ink-secondary">
              Технические детали
            </summary>
            <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap break-words rounded-md bg-bg-soft p-3 font-mono text-[11px] text-ink-secondary">
              {detail}
            </pre>
          </details>
        ) : null}

        <div className="mt-6 flex justify-end">
          <Button variant="outline" onClick={onClose}>
            Закрыть
          </Button>
        </div>
      </div>
    </div>
  );
}
