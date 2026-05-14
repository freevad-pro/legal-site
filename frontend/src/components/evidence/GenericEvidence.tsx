import type { Finding } from "@/lib/types";

export function GenericEvidence({ finding }: { finding: Finding }) {
  if (!finding.evidence) return null;
  return (
    <div className="rounded-md bg-bg-soft p-4">
      <p className="font-mono text-xs leading-relaxed text-ink-secondary whitespace-pre-wrap">
        {finding.evidence}
      </p>
    </div>
  );
}
