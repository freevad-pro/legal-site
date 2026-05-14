import type { Metadata } from "next";
import { Onest, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { AppProviders } from "@/components/providers";
import { Header } from "@/components/Header";
import { cn } from "@/lib/utils";

const onest = Onest({
  subsets: ["latin", "cyrillic"],
  weight: ["400", "500", "600", "700", "800"],
  variable: "--font-onest",
  display: "swap",
});

const jetbrains = JetBrains_Mono({
  subsets: ["latin", "cyrillic"],
  weight: ["400", "500", "700"],
  variable: "--font-jetbrains-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Legal Site — проверка сайта на соответствие законодательству РФ",
  description:
    "Введите URL — найдём нарушения законодательства РФ на сайте и подготовим отчёт со статьями, штрафами и рекомендациями.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru" className={cn(onest.variable, jetbrains.variable)}>
      <body>
        <AppProviders>
          <Header />
          <main className="min-h-[calc(100vh-64px)]">{children}</main>
        </AppProviders>
      </body>
    </html>
  );
}
