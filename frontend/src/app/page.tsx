"use client";

import { ScanForm } from "@/components/ScanForm";
import { CategoriesGrid } from "@/components/CategoriesGrid";
import { LawsMarquee } from "@/components/LawsMarquee";

export default function HomePage() {
  return (
    <>
      <section className="container pt-20 pb-12">
        <div className="mx-auto flex max-w-[860px] flex-col items-center text-center">
          <h1 className="text-[34px] font-bold leading-[1.1] sm:text-[44px] lg:text-[52px]">
            Проверим сайт на соответствие законам РФ
          </h1>
          <p className="mt-5 max-w-[620px] text-base text-ink-secondary sm:text-[17px]">
            Соберём страницы, проверим формы, политику, баннеры и реквизиты по 15 актам и 100
            нарушениям. Покажем статьи, штрафы и что исправить.
          </p>
        </div>

        <div className="mx-auto mt-10 max-w-[820px] rounded-card bg-brand p-6 text-white sm:p-8">
          <div className="mb-4 flex flex-col gap-1 text-white/90">
            <span className="text-xs font-semibold uppercase tracking-[0.14em] opacity-80">
              Начнём
            </span>
            <span className="text-[17px] font-semibold text-white">
              Введите адрес — запустим проверку
            </span>
          </div>
          <ScanForm />
        </div>
      </section>

      <CategoriesGrid />
      <LawsMarquee />
    </>
  );
}
