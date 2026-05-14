"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { getMe, login as apiLogin, logout as apiLogout } from "@/lib/api";

interface AuthState {
  login: string | null;
  loading: boolean;
  signIn: (login: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [login, setLogin] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const me = await getMe();
      setLogin(me.login);
    } catch {
      setLogin(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const signIn = useCallback(
    async (loginValue: string, password: string) => {
      const me = await apiLogin(loginValue, password);
      setLogin(me.login);
    },
    [],
  );

  const signOut = useCallback(async () => {
    await apiLogout();
    setLogin(null);
  }, []);

  return (
    <AuthContext.Provider value={{ login, loading, signIn, signOut, refresh }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
