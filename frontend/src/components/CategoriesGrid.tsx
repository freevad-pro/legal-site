"use client";

import { Lock, Cookie, Megaphone, Users, FileText, Copyright } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { LawCategory } from "@/lib/types";

interface CategoryCard {
  category: LawCategory;
  title: string;
  description: string;
  icon: LucideIcon;
}

const CARDS: readonly CategoryCard[] = [
  {
    category: "privacy",
    title: "Персональные данные",
    description: "Согласия, политика, локализация, уведомление РКН.",
    icon: Lock,
  },
  {
    category: "cookies",
    title: "Cookies",
    description: "Баннер согласия, трекинг, DNT, маркетинговые cookies.",
    icon: Cookie,
  },
  {
    category: "advertising",
    title: "Реклама",
    description: "Маркировка ERID, ОРД, требования к содержанию рекламы.",
    icon: Megaphone,
  },
  {
    category: "consumer",
    title: "Защита потребителей",
    description: "Реквизиты, оферта, возвраты, расчёты, кассовая техника.",
    icon: Users,
  },
  {
    category: "info",
    title: "Информация и контент",
    description: "Госязык, защита детей, ОРИ, электронная подпись.",
    icon: FileText,
  },
  {
    category: "copyright",
    title: "Интеллектуальная собственность",
    description: "Авторские права, товарные знаки, использование контента.",
    icon: Copyright,
  },
];

export function CategoriesGrid() {
  return (
    <section className="container pb-14">
      <h2 className="mb-6 text-2xl font-bold sm:text-[28px]">Что найдём на сайте</h2>
      <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {CARDS.map((card) => (
          <li
            key={card.category}
            className="flex flex-col gap-3 rounded-card bg-bg-soft p-6"
          >
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-white">
              <card.icon className="h-5 w-5 text-brand" />
            </div>
            <h3 className="text-[17px] font-bold text-ink-primary">{card.title}</h3>
            <p className="text-sm leading-snug text-ink-secondary">{card.description}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}
