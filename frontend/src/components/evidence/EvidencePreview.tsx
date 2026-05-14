import type { EvidenceTemplate, Finding } from "@/lib/types";
import { GenericEvidence } from "@/components/evidence/GenericEvidence";
import {
  BannerNoMarking,
  ContactsNoRequisites,
  CookiesBeforeConsent,
  DntIgnored,
  FooterNoPolicy,
  FormNoConsent,
} from "@/components/evidence/templates";

const TEMPLATES: Record<EvidenceTemplate, React.ComponentType> = {
  footer_no_policy: FooterNoPolicy,
  form_no_consent: FormNoConsent,
  cookies_before_consent: CookiesBeforeConsent,
  contacts_no_requisites: ContactsNoRequisites,
  banner_no_marking: BannerNoMarking,
  dnt_ignored: DntIgnored,
};

// finding.evidence_template — имя шаблона, проброшенное из violation.evidence_template
// (см. app/engine.py:_violation_to_finding). Если null или неизвестно — рендерим
// универсальный fallback с evidence-цитатой.
export function EvidencePreview({ finding }: { finding: Finding }) {
  const templateName = finding.evidence_template;
  if (templateName && templateName in TEMPLATES) {
    const Component = TEMPLATES[templateName];
    return <Component />;
  }
  return <GenericEvidence finding={finding} />;
}
