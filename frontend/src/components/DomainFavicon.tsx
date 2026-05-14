import { faviconColor } from "@/lib/favicon";
import { cn } from "@/lib/utils";

interface Props {
  host: string;
  size?: "sm" | "md" | "lg";
  className?: string;
}

const SIZE_CLASSES: Record<NonNullable<Props["size"]>, string> = {
  sm: "h-5 w-5 text-[10px]",
  md: "h-8 w-8 text-sm",
  lg: "h-10 w-10 text-base",
};

export function DomainFavicon({ host, size = "md", className }: Props) {
  const letter = host?.[0]?.toUpperCase() ?? "?";
  return (
    <span
      className={cn(
        "inline-flex items-center justify-center rounded-full font-bold text-white",
        SIZE_CLASSES[size],
        className,
      )}
      style={{ backgroundColor: faviconColor(host) }}
      aria-hidden
    >
      {letter}
    </span>
  );
}
