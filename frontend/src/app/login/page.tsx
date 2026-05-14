"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/lib/auth-context";
import { ApiError } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const { signIn } = useAuth();
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await signIn(login.trim(), password);
      router.push("/");
      router.refresh();
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setError("Неверный логин или пароль");
      } else {
        setError("Не удалось войти. Попробуйте ещё раз.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="container flex min-h-[calc(100vh-64px)] items-center justify-center py-12">
      <div className="w-full max-w-[420px] rounded-card border border-line bg-white p-8 shadow-sm">
        <h1 className="text-2xl font-bold text-ink-primary">Вход в Legal Site</h1>
        <p className="mt-2 text-sm text-ink-secondary">
          Войдите, чтобы запускать расширенный анализ. Базовые проверки работают и без входа.
        </p>

        <form onSubmit={onSubmit} className="mt-6 flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <Label htmlFor="login">Логин</Label>
            <Input
              id="login"
              name="login"
              autoComplete="username"
              required
              value={login}
              onChange={(event) => setLogin(event.target.value)}
              disabled={submitting}
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="password">Пароль</Label>
            <Input
              id="password"
              name="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              disabled={submitting}
            />
          </div>

          {error ? (
            <p role="alert" className="text-sm text-severity-critical">
              {error}
            </p>
          ) : null}

          <Button type="submit" disabled={submitting} className="mt-2">
            {submitting ? "Входим…" : "Войти"}
          </Button>
        </form>
      </div>
    </div>
  );
}
