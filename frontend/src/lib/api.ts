// Обёртки над HTTP-API бэка. credentials: 'include' для cookie-сессии.
// База — NEXT_PUBLIC_API_BASE; пусто в production (один origin) или http://localhost:8000 в dev.

import type { ScanSummary, UserInfo } from "@/lib/types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(detail);
    this.name = "ApiError";
  }
}

async function request(path: string, init: RequestInit = {}): Promise<Response> {
  // Content-Type ставим только когда есть body — иначе на GET-запросах ловим
  // лишний CORS preflight без пользы.
  const headers: HeadersInit = init.body ? { "Content-Type": "application/json" } : {};
  const resp = await fetch(`${API_BASE}${path}`, {
    credentials: "include",
    ...init,
    headers: {
      ...headers,
      ...(init.headers ?? {}),
    },
  });
  return resp;
}

async function json<T>(resp: Response): Promise<T> {
  if (!resp.ok) {
    let detail = `HTTP ${resp.status}`;
    try {
      const body = (await resp.json()) as { detail?: string };
      if (body?.detail) detail = body.detail;
    } catch {
      // empty body
    }
    throw new ApiError(resp.status, detail);
  }
  return (await resp.json()) as T;
}

export async function getMe(): Promise<UserInfo> {
  return json<UserInfo>(await request("/api/v1/auth/me"));
}

export async function login(loginValue: string, password: string): Promise<UserInfo> {
  return json<UserInfo>(
    await request("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ login: loginValue, password }),
    }),
  );
}

export async function logout(): Promise<void> {
  await request("/api/v1/auth/logout", { method: "POST" });
}

export async function createScan(url: string, withLlm: boolean): Promise<{ scan_id: string }> {
  return json<{ scan_id: string }>(
    await request("/api/v1/scans", {
      method: "POST",
      body: JSON.stringify({ url, with_llm: withLlm }),
    }),
  );
}

export async function getScan(scanId: string): Promise<ScanSummary> {
  return json<ScanSummary>(await request(`/api/v1/scans/${scanId}`));
}

export function reportPdfUrl(scanId: string): string {
  return `${API_BASE}/api/v1/scans/${scanId}/report.pdf`;
}

// Качаем PDF через fetch (а не `<a download>`), чтобы:
// 1) перехватить 503 от бэка (WeasyPrint без GTK runtime на Windows) и показать
//    понятный текст вместо тихого сохранения .txt с JSON-телом ошибки;
// 2) корректно отдать filename из Content-Disposition.
export async function downloadReportPdf(scanId: string, fallbackName: string): Promise<void> {
  const resp = await request(`/api/v1/scans/${scanId}/report.pdf`);
  if (!resp.ok) {
    let detail = `HTTP ${resp.status}`;
    try {
      const body = (await resp.json()) as { detail?: string };
      if (body?.detail) detail = body.detail;
    } catch {
      // empty / non-json body
    }
    throw new ApiError(resp.status, detail);
  }
  const blob = await resp.blob();
  const filename = parseFilename(resp.headers.get("content-disposition")) ?? fallbackName;
  const url = URL.createObjectURL(blob);
  try {
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
  } finally {
    URL.revokeObjectURL(url);
  }
}

function parseFilename(header: string | null): string | null {
  if (!header) return null;
  const match = /filename="?([^";]+)"?/i.exec(header);
  return match?.[1] ?? null;
}

export function eventsUrl(scanId: string): string {
  return `${API_BASE}/api/v1/scans/${scanId}/events`;
}
