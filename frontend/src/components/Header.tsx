"use client";

import Link from "next/link";
import { LogOut } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";

export function Header() {
  const { login, loading, signOut } = useAuth();

  return (
    <header className="sticky top-0 z-40 w-full border-b border-line bg-white/94 backdrop-blur supports-[backdrop-filter]:bg-white/80">
      <div className="container flex h-16 items-center justify-between">
        <Link href="/" className="flex items-center gap-2 text-ink-primary">
          <span className="inline-flex h-8 w-8 items-center justify-center rounded-md bg-brand text-white font-bold">
            L
          </span>
          <span className="font-semibold text-[15px]">Legal Site</span>
        </Link>

        <nav className="flex items-center gap-3">
          {loading ? null : login ? (
            <>
              <span className="font-mono text-sm text-ink-secondary">{login}</span>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  void signOut();
                }}
                aria-label="Выйти"
              >
                <LogOut className="h-4 w-4" />
                <span>Выйти</span>
              </Button>
            </>
          ) : (
            <Link href="/login">
              <Button variant="outline" size="sm">
                Войти
              </Button>
            </Link>
          )}
        </nav>
      </div>
    </header>
  );
}
