import type {
  EvidenceAssessment,
  IncidentResponse,
  IncidentStatus,
  RetrievedPassage,
  ToolEvidence,
} from "./types";

/** Turn snake_case enum values into readable labels: "issue_refund" -> "Issue refund". */
export function humanize(value: string | null | undefined): string {
  if (!value) return "—";
  const spaced = value.replace(/[_.]/g, " ").trim();
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

export function formatPercent(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${(value * 100).toFixed(digits)}%`;
}

export const STATUS_LABEL: Record<IncidentStatus, string> = {
  resolved: "Resolved",
  escalated: "Escalated",
  pending_human_review: "Needs review",
  error: "Error",
  unknown: "Unknown",
};

export type ConfidenceBand = "high" | "medium" | "low";

/** Banding is relative to the backend's auto-resolve threshold, not a fixed cut. */
export function confidenceBand(confidence: number, threshold: number): ConfidenceBand {
  if (confidence >= threshold) return "high";
  if (confidence >= threshold / 2) return "medium";
  return "low";
}

export type ResolvedSource =
  | { kind: "passage"; id: string; passage: RetrievedPassage }
  | { kind: "tool"; id: string; evidence: ToolEvidence[] }
  | { kind: "unknown"; id: string };

/**
 * Map a citation string from `ResolutionDecision.citations` back to the exact
 * policy passage or MCP tool result it refers to. An "unknown" result means
 * the model cited something it was never shown -- surfaced loudly in the UI.
 */
export function resolveCitation(
  citation: string,
  passages: RetrievedPassage[],
  evidence: ToolEvidence[],
): ResolvedSource {
  const id = citation.replace(/^\[?(doc|tool):/, "").replace(/\]$/, "").trim();
  const passage = passages.find((p) => p.doc_id === id);
  if (passage) return { kind: "passage", id, passage };
  const tools = evidence.filter((e) => e.source_tool === id);
  if (tools.length) return { kind: "tool", id, evidence: tools };
  return { kind: "unknown", id };
}

/** Grounded claims are emitted as "[tool:crm.get_order] Order ..." or "[doc:policy-x] ...". */
export function parseClaim(claim: string): { source: string | null; text: string } {
  const match = claim.match(/^\[(?:tool|doc):([^\]]+)\]\s*(.*)$/s);
  if (!match) return { source: null, text: claim };
  return { source: match[1], text: match[2] };
}

/** Why a case needs a person, in one line -- shown in the review queue. */
export function reviewReason(incident: IncidentResponse): string {
  return incident.pending_review?.reason ?? incident.escalation?.reason ?? "Awaiting human review.";
}

export function citationCoverage(incident: IncidentResponse): { cited: number; unknown: number } {
  const citations = incident.decision?.citations ?? [];
  let unknown = 0;
  for (const c of citations) {
    if (resolveCitation(c, incident.retrieved_passages, incident.tool_evidence).kind === "unknown") unknown++;
  }
  return { cited: citations.length, unknown };
}

export function assessmentOf(incident: IncidentResponse): EvidenceAssessment | null {
  return incident.assessment ?? incident.pending_review?.assessment ?? null;
}
