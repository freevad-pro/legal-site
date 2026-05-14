import * as React from "react";
import { cn } from "@/lib/utils";

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  tone?: "neutral" | "brand" | "critical" | "high" | "medium" | "low" | "inconclusive";
}

const toneClasses: Record<NonNullable<BadgeProps["tone"]>, string> = {
  neutral: "bg-bg-soft text-ink-secondary border-line",
  brand: "bg-brand-soft text-brand border-brand/30",
  critical: "bg-severity-critical-soft text-severity-critical border-severity-critical-border",
  high: "bg-severity-high-soft text-severity-high border-severity-high-border",
  medium: "bg-severity-medium-soft text-severity-medium border-severity-medium-border",
  low: "bg-severity-low-soft text-severity-low border-severity-low-border",
  inconclusive:
    "bg-severity-inconclusive-soft text-severity-inconclusive border-severity-inconclusive-border",
};

export function Badge({ tone = "neutral", className, ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-semibold",
        toneClasses[tone],
        className,
      )}
      {...props}
    />
  );
}
