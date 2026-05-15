import type { Finding } from "@/lib/types";

// Fallback-превью: показываем evidence (найденный фрагмент сайта) и/или explanation
// (почему упала проверка). Раньше показывали только evidence — но у большинства
// детерминированных чеков evidence=null, а вся информация лежит в explanation
// ("missing keywords in main page text: [...]"). PDF выводит оба поля — UI должен тоже.
export function GenericEvidence({ finding }: { finding: Finding }) {
  if (!finding.evidence && !finding.explanation) return null;
  return (
    <div className="flex flex-col gap-2">
      {finding.evidence ? (
        <div className="rounded-md bg-bg-soft p-4">
          <p className="font-mono text-xs leading-relaxed text-ink-secondary whitespace-pre-wrap">
            {finding.evidence}
          </p>
        </div>
      ) : null}
      {finding.explanation ? (
        <p className="text-sm leading-snug text-ink-secondary whitespace-pre-wrap">
          {finding.explanation}
        </p>
      ) : null}
    </div>
  );
}
