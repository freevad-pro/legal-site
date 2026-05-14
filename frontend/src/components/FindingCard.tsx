"use client";

import { ChevronDown } from "lucide-react";
import { EvidencePreview } from "@/components/evidence/EvidencePreview";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { Finding, Severity } from "@/lib/types";

const SEVERITY_LABEL: Record<Severity, string> = {
  critical: "Критический",
  high: "Высокий",
  medium: "Средний",
  low: "Низкий",
};

const SEVERITY_TONE: Record<Severity, "critical" | "high" | "medium" | "low"> = {
  critical: "critical",
  high: "high",
  medium: "medium",
  low: "low",
};

// Цвета — из палитры docs/design.md §5.2. Здесь дублируются, потому что inset-stripe
// нужно задать как CSS box-shadow, а Tailwind arbitrary values не поддерживают
// токены динамически.
const SEVERITY_STRIPE_COLOR: Record<Severity, string> = {
  critical: "#C73C3C",
  high: "#D87A1A",
  medium: "#C99A1F",
  low: "#3E7FBF",
};

function formatPenaltyRange(min: number | null, max: number | null): string {
  if (min === null && max === null) return "сумма уточняется";
  if (min !== null && max !== null)
    return `${min.toLocaleString("ru-RU")}–${max.toLocaleString("ru-RU")} ₽`;
  return `${(min ?? max ?? 0).toLocaleString("ru-RU")} ₽`;
}

interface Props {
  finding: Finding;
  expanded: boolean;
  onToggle: () => void;
}

export function FindingCard({ finding, expanded, onToggle }: Props) {
  return (
    <article
      className={cn("rounded-card border border-line bg-white")}
      style={{ boxShadow: `inset 3px 0 0 ${SEVERITY_STRIPE_COLOR[finding.severity]}` }}
    >
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-start justify-between gap-4 p-5 text-left"
        aria-expanded={expanded}
      >
        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-2">
            <Badge tone={SEVERITY_TONE[finding.severity]}>
              {SEVERITY_LABEL[finding.severity]}
            </Badge>
            <span className="font-mono text-xs text-ink-secondary">{finding.article}</span>
          </div>
          <h3 className="text-[17px] font-semibold leading-snug text-ink-primary">
            {finding.title}
          </h3>
        </div>
        <ChevronDown
          className={cn(
            "mt-1 h-5 w-5 shrink-0 text-ink-secondary transition-transform",
            expanded && "rotate-180",
          )}
        />
      </button>

      {expanded ? (
        <div className="flex flex-col gap-4 border-t border-line px-5 pb-5 pt-4">
          <div>
            <p className="eyebrow mb-2">Где найдено</p>
            <EvidencePreview finding={finding} />
          </div>

          {finding.recommendation ? (
            <div>
              <p className="eyebrow mb-2">Что сделать</p>
              <p className="text-sm text-ink-primary whitespace-pre-wrap">
                {finding.recommendation}
              </p>
            </div>
          ) : null}

          {finding.penalties.length > 0 ? (
            <div>
              <p className="eyebrow mb-2">Штрафы</p>
              <ul className="flex flex-col gap-1 text-xs text-ink-secondary">
                {finding.penalties.map((p, i) => (
                  <li key={`${p.coap_article}-${p.subject}-${i}`}>
                    <span className="font-mono text-ink-primary">
                      {formatPenaltyRange(p.amount_min, p.amount_max)}
                    </span>{" "}
                    — {subjectLabel(p.subject)} · {p.coap_article}
                    {p.notes ? ` · ${p.notes}` : ""}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      ) : null}
    </article>
  );
}

function subjectLabel(subject: string): string {
  return {
    citizen: "гражданин",
    official: "должностное лицо",
    sole_proprietor: "ИП",
    small_org: "малое предприятие",
    organization: "организация",
  }[subject] ?? subject;
}
