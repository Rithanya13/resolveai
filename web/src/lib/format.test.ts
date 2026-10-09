import { describe, expect, it } from "vitest";
import {
  citationCoverage,
  confidenceBand,
  formatPercent,
  humanize,
  parseClaim,
  resolveCitation,
} from "./format";
import type { IncidentResponse, RetrievedPassage, ToolEvidence } from "./types";

const passages: RetrievedPassage[] = [
  { doc_id: "policy-refunds-001", title: "Refund Policy", text: "Refunds within 30 days.", score: 0.03 },
];
const evidence: ToolEvidence[] = [
  { source_tool: "crm.get_order", summary: "Order order_5004 amount=$899", raw: { found: true } },
  { source_tool: "crm.get_order", summary: "Order order_5005 amount=$12", raw: { found: true } },
];

describe("resolveCitation", () => {
  it("maps a doc id to its retrieved passage", () => {
    const r = resolveCitation("policy-refunds-001", passages, evidence);
    expect(r.kind).toBe("passage");
  });

  it("maps a tool name to every matching MCP result", () => {
    const r = resolveCitation("crm.get_order", passages, evidence);
    expect(r.kind).toBe("tool");
    if (r.kind === "tool") expect(r.evidence).toHaveLength(2);
  });

  it("accepts prefixed forms like [tool:x]", () => {
    expect(resolveCitation("[tool:crm.get_order]", passages, evidence).kind).toBe("tool");
    expect(resolveCitation("doc:policy-refunds-001", passages, evidence).kind).toBe("passage");
  });

  it("flags citations the model was never shown", () => {
    expect(resolveCitation("policy-made-up-999", passages, evidence).kind).toBe("unknown");
  });
});

describe("parseClaim", () => {
  it("splits the source tag from the claim text", () => {
    expect(parseClaim("[tool:crm.get_customer] Customer on file.")).toEqual({
      source: "crm.get_customer",
      text: "Customer on file.",
    });
  });

  it("leaves untagged claims alone", () => {
    expect(parseClaim("No evidence.")).toEqual({ source: null, text: "No evidence." });
  });
});

describe("confidenceBand", () => {
  it("is relative to the auto-resolve threshold", () => {
    expect(confidenceBand(0.9, 0.72)).toBe("high");
    expect(confidenceBand(0.72, 0.72)).toBe("high");
    expect(confidenceBand(0.5, 0.72)).toBe("medium");
    expect(confidenceBand(0.15, 0.72)).toBe("low");
  });
});

describe("citationCoverage", () => {
  it("counts citations that do not resolve to any source", () => {
    const incident = {
      retrieved_passages: passages,
      tool_evidence: evidence,
      decision: {
        action: "issue_refund",
        customer_message: "",
        internal_notes: "",
        citations: ["policy-refunds-001", "ghost-doc"],
      },
    } as unknown as IncidentResponse;
    expect(citationCoverage(incident)).toEqual({ cited: 2, unknown: 1 });
  });
});

describe("formatting helpers", () => {
  it("humanizes enum values", () => {
    expect(humanize("issue_refund")).toBe("Issue refund");
    expect(humanize("crm.get_order")).toBe("Crm get order");
    expect(humanize(null)).toBe("—");
  });

  it("formats percentages", () => {
    expect(formatPercent(0.9)).toBe("90%");
    expect(formatPercent(undefined)).toBe("—");
  });
});
