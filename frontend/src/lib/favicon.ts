// Цвет фавикона домена по хешу host'а — для визуальной узнаваемости сайта в прогрессе/отчёте.

const COLORS = [
  "#2563EB",
  "#7C3AED",
  "#DB2777",
  "#DC2626",
  "#EA580C",
  "#CA8A04",
  "#16A34A",
  "#0891B2",
  "#4F46E5",
];

export function faviconColor(host: string): string {
  let h = 0;
  for (let i = 0; i < host.length; i++) {
    h = (h * 31 + host.charCodeAt(i)) % COLORS.length;
  }
  return COLORS[h];
}

export function hostFromUrl(rawUrl: string): string {
  try {
    return new URL(rawUrl).host;
  } catch {
    return rawUrl;
  }
}

export function auditNumber(scanId: string, startedAt: string): string {
  const head = scanId.replace(/-/g, "").slice(0, 4).toUpperCase();
  const d = new Date(startedAt);
  if (Number.isNaN(d.getTime())) return head;
  return `${head}-${d.getMonth() + 1}${String(d.getDate()).padStart(2, "0")}`;
}
