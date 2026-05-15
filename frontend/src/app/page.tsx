"use client";

import { ScanForm } from "@/components/ScanForm";
import { CategoriesGrid } from "@/components/CategoriesGrid";
import { LawsMarquee } from "@/components/LawsMarquee";

export default function HomePage() {
  return (
    <>
      <section className="container pt-20 pb-12">
        <h1 className="max-w-[860px] text-[34px] font-bold leading-[1.1] sm:text-[44px] lg:text-[52px]">
          Проверим сайт на соответствие законам РФ
        </h1>
        <p className="mt-5 max-w-[620px] text-base text-ink-secondary sm:text-[17px]">
          Соберём страницы, проверим формы, политику, баннеры и реквизиты по 15 актам и 100
          нарушениям. Покажем статьи, штрафы и что исправить.
        </p>

        <div
          className="relative mt-10 overflow-hidden rounded-card bg-brand p-6 text-white sm:p-10 lg:p-12"
          style={{
            backgroundImage:
              "radial-gradient(rgba(255,255,255,0.10) 1.5px, transparent 1.5px)",
            backgroundSize: "22px 22px",
          }}
        >
          {/* Декоративная эмблема в правом нижнем углу — концентрические круги с галочкой. */}
          <svg
            aria-hidden
            className="pointer-events-none absolute -right-10 -bottom-10 hidden opacity-15 sm:block"
            width="280"
            height="280"
            viewBox="0 0 280 280"
            fill="none"
          >
            <circle cx="140" cy="140" r="135" stroke="white" strokeWidth="2" />
            <circle cx="140" cy="140" r="95" stroke="white" strokeWidth="2" />
            <circle cx="140" cy="140" r="55" stroke="white" strokeWidth="2" />
            <path
              d="M85 140L125 180L195 110"
              stroke="white"
              strokeWidth="3"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>

          <div className="relative">
            <h2 className="mb-6 text-[24px] font-bold leading-tight sm:text-[32px]">
              Проверьте сайт прямо сейчас
            </h2>
            <div className="max-w-[820px]">
              <ScanForm />
            </div>
          </div>
        </div>
      </section>

      <CategoriesGrid />
      <LawsMarquee />
    </>
  );
}
