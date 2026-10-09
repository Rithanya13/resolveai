// TypeScript mirrors of the Pydantic contracts in `src/resolveai/schemas.py`
// and the response shape built in `src/resolveai/api/routes.py`.
// Keep these in sync with the backend: the UI never parses free text.

export type IncidentCategory =
  | "order_not_received"
  | "refund_request"
  | "account_access"
  | "billing_discrepancy"
  | "other";

export type ResolutionAction =
  | "issue_refund"
  | "resend_order"
  | "reset_account_access"
  | "correct_billing"
  | "no_action_needed"
  | "escalate_to_human";

export type IncidentStatus = "resolved" | "escalated" | "pending_human_review" | "error" | "unknown";

export interface Incident {
  incident_id: string;
  customer_id: string;
  subject: string;
  description: string;
}

export interface IncidentClassification {
  category: IncidentCategory;
  urgency: number;
  rationale: string;
}

export interface RetrievedPassage {
  doc_id: string;
  title: string;
  text: string;
  score: number;
}

export interface ToolEvidence {
  source_tool: string;
  summary: string;
  raw: Record<string, unknown>;
}

export interface EvidenceAssessment {
  is_sufficient: boolean;
  confidence: number;
  grounded_claims: string[];
  unsupported_claims: string[];
  missing_evidence: string[];
}

export interface ResolutionDecision {
  action: ResolutionAction;
  customer_message: string;
  internal_notes: string;
  citations: string[];
}

export interface EscalationRequest {
  incident_id: string;
  reason: string;
  assessment: EvidenceAssessment;
  recommended_action: ResolutionAction | null;
}

export interface PendingReview {
  incident_id: string;
  reason: string;
  assessment: EvidenceAssessment;
  recommended_action: ResolutionAction | null;
  proposed_customer_message: string | null;
}

export interface IncidentResponse {
  incident_id: string;
  status: IncidentStatus;
  incident: Incident | null;
  trace: string[];
  retrieved_passages: RetrievedPassage[];
  tool_evidence: ToolEvidence[];
  order_amount_usd: number | null;
  confidence_threshold: number;
  classification: IncidentClassification | null;
  assessment: EvidenceAssessment | null;
  decision: ResolutionDecision | null;
  escalation: EscalationRequest | null;
  pending_review?: PendingReview;
}

export interface SubmitIncidentRequest {
  customer_id: string;
  subject: string;
  description: string;
}

export interface ApprovalRequest {
  approved: boolean;
  note?: string;
  action?: ResolutionAction;
  customer_message?: string;
}

export interface EvalCaseResult {
  case_id: string;
  expected_category: string;
  actual_category: string | null;
  expected_outcome: "auto_resolved" | "human_review";
  actual_outcome: "auto_resolved" | "human_review";
  grounded: boolean;
}

export interface EvalReport {
  cases: number;
  metrics: {
    category_accuracy: number;
    outcome_accuracy: number;
    escalation_precision: number;
    escalation_recall: number;
    groundedness_rate: number;
  };
  results: EvalCaseResult[];
}
