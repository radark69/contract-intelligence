export type DocumentStatus =
  | "uploaded"
  | "processing"
  | "extracted"
  | "analyzed"
  | "reported"
  | "failed";

export type Severity = "critical" | "high" | "medium" | "low" | "informational";

export interface DocSummary {
  id: string;
  filename: string;
  status: DocumentStatus;
  document_type: string;
  client: string | null;
  contract_value: number | null;
  created_at: string;
}

export interface DocumentDetail {
  id: string;
  filename: string;
  status: DocumentStatus;
  file_hash: string;
  document_type: string;
  file_size: number | null;
  client: string | null;
  contractor: string | null;
  contract_type: string | null;
  currency: string | null;
  contract_value: number | null;
  start_date: string | null;
  end_date: string | null;
  version: string | null;
  page_count: number | null;
  sheet_count: number | null;
  error_message: string | null;
  warnings: string[] | null;
  created_at: string;
  updated_at: string;
}

export interface Finding {
  id: string;
  clause_id: string | null;
  category: string;
  severity: Severity;
  confidence: number;
  finding: string;
  risk: string;
  impact: string | null;
  recommendation: string;
  dbs_policy_rule: string | null;
  source_reference: string;
  source_text: string;
  financial_impact: number | null;
}

export interface RegisterRow {
  id: string;
  severity: Severity;
  category: string;
  clause: string;
  finding: string;
  exposure: number | null;
  dbs_position: string;
  required_action: string;
  dbs_policy_rule: string | null;
}

export interface RiskRegister {
  document_id: string;
  total: number;
  severity_counts: Partial<Record<Severity, number>>;
  management_approval_rule_ids: string[];
  rows: RegisterRow[];
}

export interface Exposure {
  id: string;
  scenario: string;
  result: number;
  currency: string | null;
  formula: string;
  assumption: string;
  source_reference: string;
}

export interface CannotCalculate {
  metric: string;
  reason: string;
}

export interface ExposuresResponse {
  exposures: Exposure[];
  cannot_calculate: CannotCalculate[];
}

export interface Obligation {
  id: string;
  party: string;
  obligation: string;
  trigger: string | null;
  frequency: string | null;
  source_reference: string;
}

export interface Fact {
  id: string;
  key: string;
  label: string;
  value: unknown;
  raw_value: string | null;
  confidence: number;
  source_reference: string;
  source_text: string;
  clause_id: string | null;
}
