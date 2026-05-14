"use client";

import { LAWS } from "@/data/laws.generated";
import { getIcon } from "@/lib/icons";

export function LawsMarquee() {
  // Дублируем список — даёт бесшовную петлю.
  const items = [...LAWS, ...LAWS];

  return (
    <section className="border-y border-line bg-bg-soft py-12">
      <div className="container mb-6 flex flex-col gap-2">
        <span className="eyebrow">Что в корпусе</span>
        <h2 className="text-2xl font-bold sm:text-[28px]">
          {LAWS.length} актов, {LAWS.reduce((s, l) => s + l.violationsCount, 0)} нарушений
        </h2>
      </div>

      <div className="group relative overflow-hidden">
        <div className="flex w-max gap-3 animate-marquee group-hover:[animation-play-state:paused]">
          {items.map((law, idx) => {
            const Icon = getIcon(law.icon);
            return (
              <article
                key={`${law.id}-${idx}`}
                className="flex w-[280px] shrink-0 flex-col gap-3 rounded-card border border-line bg-white p-5 transition-colors hover:bg-bg-gray"
              >
                <div className="flex h-10 w-10 items-center justify-center rounded-md bg-bg-soft transition-colors group-hover:bg-brand-soft">
                  <Icon className="h-5 w-5 text-ink-primary transition-colors group-hover:text-brand" />
                </div>
                <h3 className="font-mono text-sm font-semibold text-ink-secondary">
                  {law.shortTitle}
                </h3>
                <p className="text-[15px] font-semibold text-ink-primary leading-snug">
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
    </section>
  );
}
