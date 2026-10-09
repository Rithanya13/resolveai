"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ConfidenceMeter } from "@/components/ConfidenceMeter";
import { ErrorNote } from "@/components/ErrorNote";
import { ReviewPanel } from "@/components/ReviewPanel";
import { sourceAnchor, Sources } from "@/components/Sources";
import { StatusBadge } from "@/components/StatusBadge";
import { TracePipeline } from "@/components/TracePipeline";
import { api, ApiError } from "@/lib/api";
import { assessmentOf, citationCoverage, humanize, parseClaim, resolveCitation } from "@/lib/format";
import type { IncidentResponse } from "@/lib/types";

export default function IncidentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [incident, setIncident] = useState<IncidentResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [highlight, setHighlight] = useState<string | null>(null);

  useEffect(() => {
    api
      .getIncident(id)
      .then(setIncident)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Failed to load incident."));
  }, [id]);

  function focusSource(sourceId: string) {
    setHighlight(sourceId);
    document.getElementById(sourceAnchor(sourceId))?.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  if (error) return <div style={{ paddingTop: 24 }}><ErrorNote error={error} /></div>;
  if (!incident) return <div className="empty">Loading…</div>;

  const paused = incident.status === "pending_human_review";
  const assessment = assessmentOf(incident);
  const decision = incident.decision;
  const coverage = citationCoverage(incident);

  return (
    <>
      <div className="page-head">
        <div>
          <div className="hint">
            <Link href="/">Incidents</Link> / <span className="mono">{incident.incident_id}</span>
          </div>
          <h1>{incident.incident?.subject ?? incident.incident_id}</h1>
          <p>{incident.incident?.description}</p>
        </div>
        <StatusBadge status={incident.status} />
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <h2>Execution trace</h2>
        <TracePipeline trace={incident.trace} paused={paused} />
      </div>

      <div className="grid grid-main">
        <div className="stack">
          {paused && (
            <section className="card">
              <h2>Human review required</h2>
              <ReviewPanel incident={incident} onDone={setIncident} />
            </section>
          )}

          <section className="card">
            <h2>{paused && decision ? "Proposed resolution" : "Resolution"}</h2>
            {paused && decision && (
              <div className="callout callout-warn">Not executed. Nothing has been sent to the customer until a reviewer approves.</div>
            )}
            {!decision ? (
              <div className="muted">
                {paused ? "No autonomous decision. The agent handed this case to a person." : "No decision recorded."}
              </div>
            ) : (
              <>
                <dl className="kv" style={{ marginBottom: 12 }}>
                  <dt>Action</dt>
                  <dd>
                    <strong>{humanize(decision.action)}</strong>
                  </dd>
                  {incident.order_amount_usd != null && (
                    <>
                      <dt>Order value</dt>
                      <dd>${incident.order_amount_usd.toFixed(2)}</dd>
                    </>
                  )}
                </dl>
                <label>{paused ? "Drafted answer to customer" : "Answer to customer"}</label>
                <blockquote className="quote">{decision.customer_message}</blockquote>
                <div style={{ marginTop: 12 }}>
                  <label>
                    Citations{" "}
                    <span className="hint">
                      ({coverage.cited} cited
                      {coverage.unknown > 0 ? `, ${coverage.unknown} not found in sources` : ", all traceable"})
                    </span>
                  </label>
                  {decision.citations.length === 0 ? (
                    <div className="callout callout-warn">This decision cites no sources.</div>
                  ) : (
                    <div className="btn-row">
                      {decision.citations.map((c) => {
                        const resolved = resolveCitation(c, incident.retrieved_passages, incident.tool_evidence);
                        const label = resolved.kind === "passage" ? resolved.passage.title : resolved.id;
                        return (
                          <button
                            key={c}
                            type="button"
                            className={`cite ${resolved.kind === "unknown" ? "unknown" : ""}`}
                            title={resolved.kind === "unknown" ? "Not found in retrieved sources" : "Show source"}
                            onClick={() => resolved.kind !== "unknown" && focusSource(resolved.id)}
                          >
                            {label}
                          </button>
                        );
                      })}
                    </div>
                  )}
                </div>
                <details style={{ marginTop: 12 }}>
                  <summary>Internal notes</summary>
                  <pre>{decision.internal_notes}</pre>
                </details>
              </>
            )}
          </section>

          <section className="card">
            <h2>Evidence assessment</h2>
            {!assessment ? (
              <div className="muted">Not assessed.</div>
            ) : (
              <>
                <ConfidenceMeter confidence={assessment.confidence} threshold={incident.confidence_threshold} />
                <div className="grid grid-2" style={{ marginTop: 16 }}>
                  <div>
                    <h3>Grounded claims</h3>
                    {assessment.grounded_claims.length === 0 ? (
                      <div className="muted">None.</div>
                    ) : (
                      <ul className="claims">
                        {assessment.grounded_claims.map((claim, i) => {
                          const { source, text } = parseClaim(claim);
                          return (
                            <li key={i} className="ok">
                              {source && (
                                <button type="button" className="tag" onClick={() => focusSource(source)}>
                                  {source}
                                </button>
                              )}
                              {text}
                            </li>
                          );
                        })}
                      </ul>
                    )}
                  </div>
                  <div>
                    <h3>Gaps</h3>
                    {assessment.unsupported_claims.length + assessment.missing_evidence.length === 0 ? (
                      <div className="muted">None.</div>
                    ) : (
                      <ul className="claims">
                        {assessment.unsupported_claims.map((c, i) => (
                          <li key={`u${i}`} className="bad">
                            <span className="tag">unsupported</span>
                            {c}
                          </li>
                        ))}
                        {assessment.missing_evidence.map((c, i) => (
                          <li key={`m${i}`} className="warn">
                            <span className="tag">missing</span>
                            {c}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                </div>
              </>
            )}
          </section>

          {incident.classification && (
            <section className="card">
              <h2>Classification</h2>
              <dl className="kv">
                <dt>Category</dt>
                <dd>{humanize(incident.classification.category)}</dd>
                <dt>Urgency</dt>
                <dd>{incident.classification.urgency} / 5</dd>
                <dt>Rationale</dt>
                <dd className="muted">{incident.classification.rationale}</dd>
                <dt>Customer</dt>
                <dd className="mono">{incident.incident?.customer_id}</dd>
              </dl>
            </section>
          )}
        </div>

        <aside className="card">
          <h2>Sources the agent saw</h2>
          <Sources passages={incident.retrieved_passages} evidence={incident.tool_evidence} highlight={highlight} />
        </aside>
      </div>
    </>
  );
}
