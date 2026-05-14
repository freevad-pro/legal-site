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
    <section className="container py-16">
      <div className="mb-8 flex flex-col gap-2">
        <span className="eyebrow">Что найдём</span>
        <h2 className="text-2xl font-bold sm:text-[28px]">
          Шесть зон, по которым ходит проверка
        </h2>
      </div>
      <ul className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
        {CARDS.map((card) => (
          <li
            key={card.category}
            className="flex flex-col gap-3 rounded-card bg-bg-soft p-6"
          >
            <card.icon className="h-7 w-7 text-ink-primary" />
            <h3 className="text-[17px] font-bold text-ink-primary">{card.title}</h3>
            <p className="text-sm text-ink-secondary">{card.description}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}
