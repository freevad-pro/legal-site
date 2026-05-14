// Читает docs/laws/index.yml и пишет frontend/src/data/laws.generated.ts
// + frontend/src/data/categories.generated.ts.
// Запускается из package.json как prebuild и predev.

import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { parse } from "yaml";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, "..", "..");
const INDEX_YML = resolve(ROOT, "docs", "laws", "index.yml");
const OUT_DIR = resolve(__dirname, "..", "src", "data");
const OUT_LAWS = resolve(OUT_DIR, "laws.generated.ts");
const OUT_CATEGORIES = resolve(OUT_DIR, "categories.generated.ts");

const raw = readFileSync(INDEX_YML, "utf8");
const index = parse(raw);

const laws = (index.laws ?? []).map((law) => ({
  id: law.id,
  shortTitle: law.short_title,
  title: law.title,
  category: law.category,
  icon: law.icon,
  shortDescription: law.short_description,
  violationsCount: law.violations_count,
}));

const categories = (index.categories ?? []).map((c) => ({
  category: c.category,
  violationsCount: c.violations_count,
}));

mkdirSync(OUT_DIR, { recursive: true });

const banner =
  "// Сгенерировано из docs/laws/index.yml через frontend/scripts/build-corpus.mjs.\n" +
  "// Не править руками — правьте YAML-фронтматтер закона и пересоберите make corpus.\n\n";

writeFileSync(
  OUT_LAWS,
  banner +
    'import type { LawCategory } from "@/lib/types";\n\n' +
    "export interface LawMeta {\n" +
    "  id: string;\n" +
    "  shortTitle: string;\n" +
    "  title: string;\n" +
    "  category: LawCategory;\n" +
    "  icon: string;\n" +
    "  shortDescription: string;\n" +
    "  violationsCount: number;\n" +
    "}\n\n" +
    "export const LAWS: readonly LawMeta[] = " +
    JSON.stringify(laws, null, 2) +
    " as const;\n",
  "utf8",
);

writeFileSync(
  OUT_CATEGORIES,
  banner +
    'import type { LawCategory } from "@/lib/types";\n\n' +
    "export interface CategoryAgg {\n" +
    "  category: LawCategory;\n" +
    "  violationsCount: number;\n" +
    "}\n\n" +
    "export const CATEGORY_TOTALS: readonly CategoryAgg[] = " +
    JSON.stringify(categories, null, 2) +
    " as const;\n",
  "utf8",
);

console.log(
  `corpus bundled: ${laws.length} laws, ${categories.length} categories ` +
    `(${categories.map((c) => `${c.category}=${c.violationsCount}`).join(", ")})`,
);
