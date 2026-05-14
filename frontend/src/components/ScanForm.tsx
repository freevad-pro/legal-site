"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { LlmToggle } from "@/components/LlmToggle";
import { ApiError, createScan } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

// Лёгкая проверка: либо явная http(s)-схема, либо «хоть что-то с точкой».
// Полноценная нормализация и валидация — на бэке (app/url.py); сюда попадает
// только защита от пустоты и совсем мусора, поэтому пропускаем кириллические
// домены (РФ-зоны), хосты с дефисами и портами.
const URL_PATTERN = /^(?:https?:\/\/\S+|[^\s.]+\.\S+)$/i;

export function ScanForm() {
  const router = useRouter();
  const { login } = useAuth();
  const authenticated = Boolean(login);

  const [url, setUrl] = useState("");
  const [withLlm, setWithLlm] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  function validate(value: string): string | null {
    const trimmed = value.trim();
    if (!trimmed) return "Введите адрес сайта";
    if (!URL_PATTERN.test(trimmed)) return "Похоже, это не похоже на адрес сайта";
    return null;
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    const localError = validate(url);
    if (localError) {
      setError(localError);
      return;
    }

    setSubmitting(true);
    try {
      const { scan_id } = await createScan(url.trim(), authenticated && withLlm);
      router.push(`/scan?id=${scan_id}&phase=progress`);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 401) {
          setError("Расширенный анализ доступен только после входа.");
        } else if (err.status === 422) {
          setError("Не удалось понять адрес. Попробуйте формат example.ru.");
        } else {
          setError(err.detail);
        }
      } else {
        setError("Не получилось запустить проверку. Попробуйте ещё раз.");
      }
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-4">
      <div className="flex flex-col gap-3 sm:flex-row">
        <Input
          name="url"
          inputMode="url"
          autoComplete="url"
          placeholder="example.ru"
          value={url}
          onChange={(event) => setUrl(event.target.value)}
          disabled={submitting}
          className="h-14 flex-1 bg-white text-base"
          aria-label="Адрес сайта для проверки"
        />
        <Button
          type="submit"
          variant="dark"
          size="lg"
          disabled={submitting}
          className="h-14"
        >
          <span>{submitting ? "Запускаем…" : "Проверить"}</span>
          {!submitting && <ArrowRight className="h-4 w-4" />}
        </Button>
      </div>

      <LlmToggle
        authenticated={authenticated}
        enabled={withLlm}
        onChange={setWithLlm}
      />

      {error ? (
        <p role="alert" className="text-sm text-white/90">
          {error}
        </p>
      ) : null}
    </form>
  );
}
