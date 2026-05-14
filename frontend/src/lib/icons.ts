// Маппинг Lucide kebab-имён в компоненты-иконки.
// Используется в карусели законов и витрине категорий — там, где имя приходит из данных.

import type { LucideIcon } from "lucide-react";
import {
  Circle,
  Copyright,
  CreditCard,
  Cookie,
  Database,
  FileText,
  Languages,
  Lock,
  Megaphone,
  PenTool,
  Receipt,
  Scroll,
  Shield,
  ShieldCheck,
  ShoppingCart,
  Tag,
  Users,
} from "lucide-react";

const ICONS: Record<string, LucideIcon> = {
  circle: Circle,
  cookie: Cookie,
  copyright: Copyright,
  "credit-card": CreditCard,
  database: Database,
  "file-text": FileText,
  languages: Languages,
  lock: Lock,
  megaphone: Megaphone,
  "pen-tool": PenTool,
  receipt: Receipt,
  scroll: Scroll,
  shield: Shield,
  "shield-check": ShieldCheck,
  "shopping-cart": ShoppingCart,
  tag: Tag,
  users: Users,
};

export function getIcon(name: string): LucideIcon {
  return ICONS[name] ?? Circle;
}
