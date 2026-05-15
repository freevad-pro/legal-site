// TS-зеркало Pydantic-моделей из app/api/scan.py и app/engine.py.
// Менять синхронно с бэком.

export type Severity = "low" | "medium" | "high" | "critical";
export type FindingStatus = "pass" | "fail" | "inconclusive";
export type InconclusiveReason =
  | "check_not_implemented"
  | "context_dependent"
  | "evidence_missing";

export type LawCategory =
  | "privacy"
  | "cookies"
  | "advertising"
  | "consumer"
  | "info"
  | "copyright";

export type EvidenceTemplate =
  | "footer_no_policy"
  | "form_no_consent"
  | "cookies_before_consent"
  | "contacts_no_requisites"
  | "banner_no_marking"
  | "dnt_ignored";

export interface Penalty {
  subject: "citizen" | "official" | "sole_proprietor" | "small_org" | "organization";
  coap_article: string;
  amount_min: number | null;
  amount_max: number | null;
  currency: "RUB";
  notes: string | null;
}

export interface Finding {
  violation_id: string;
  law_id: string;
  title: string;
  article: string;
  severity: Severity;
  status: FindingStatus;
  evidence: string | null;
  explanation: string | null;
  recommendation: string;
  penalties: Penalty[];
  evidence_template: EvidenceTemplate | null;
  inconclusive_reason: InconclusiveReason | null;
}

export interface ScanResult {
  url: string;
  started_at: string;
  finished_at: string;
  findings: Finding[];
  error: string | null;
}

export type ScanStatus = "pending" | "running" | "done" | "error";

export interface ScanSummary {
  scan_id: string;
  url: string;
  status: ScanStatus;
  with_llm: boolean;
  started_at: string;
  finished_at: string | null;
  error: string | null;
  result: ScanResult | null;
}

export interface UserInfo {
  login: string | null;
}

export interface SseViolationPayload {
  violation_id: string;
  law_id: string;
  title: string;
  status: FindingStatus;
  severity: Severity;
}

export interface SseDonePayload {
  summary: { passed: number; failed: number; inconclusive: number };
  error?: string;
}
