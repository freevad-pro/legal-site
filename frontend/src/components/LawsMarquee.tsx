"use client";

import { LAWS } from "@/data/laws.generated";
import { getIcon } from "@/lib/icons";

export function LawsMarquee() {
  // Дублируем список — даёт бесшовную петлю.
  const items = [...LAWS, ...LAWS];

  return (
    <section className="border-t border-line bg-bg-base py-12">
      <div className="container">
        <div className="mb-6 flex flex-wrap items-end justify-between gap-2">
          <h2 className="text-2xl font-bold sm:text-[28px]">На соответствие чему проверяем</h2>
          <span className="text-sm text-ink-muted">
            {LAWS.length} актов · {LAWS.reduce((s, l) => s + l.violationsCount, 0)} проверок
          </span>
        </div>

        <div className="group overflow-hidden rounded-card">
          <div className="flex w-max gap-3 animate-marquee group-hover:[animation-play-state:paused]">
            {items.map((law, idx) => {
              const Icon = getIcon(law.icon);
              return (
                <article
                  key={`${law.id}-${idx}`}
                  className="group/card flex w-[260px] shrink-0 flex-col gap-3 rounded-card bg-bg-soft p-5 transition-colors hover:bg-bg-gray sm:w-[280px]"
                >
                  <div className="flex h-12 w-12 items-center justify-center rounded-full bg-white transition-all group-hover/card:scale-110 group-hover/card:bg-brand">
                    <Icon className="h-5 w-5 text-brand transition-colors group-hover/card:text-white" />
                  </div>
                  <h3 className="font-mono text-sm font-semibold text-ink-secondary">
                    {law.shortTitle}
                  </h3>
                  <p className="text-[15px] font-semibold leading-snug text-ink-primary">
                    {law.shortDescription}
                  </p>
                  <p className="mt-auto text-xs text-ink-secondary">
                    {law.violationsCount} проверок
                  </p>
                </article>
              );
            })}
          </div>
        </div>
      </div>
    </section>
  );
}
