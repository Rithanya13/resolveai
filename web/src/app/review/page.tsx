"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { ErrorNote } from "@/components/ErrorNote";
import { ReviewPanel } from "@/components/ReviewPanel";
import { StatusBadge } from "@/components/StatusBadge";
import { api, ApiError } from "@/lib/api";
import { assessmentOf, formatPercent, humanize, reviewReason } from "@/lib/format";
import type { IncidentResponse } from "@/lib/types";

export default function ReviewQueuePage() {
  const [queue, setQueue] = useState<IncidentResponse[] | null>(null);
  const [done, setDone] = useState<IncidentResponse[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const all = await api.listIncidents();
      setQueue(all.filter((i) => i.status === "pending_human_review"));
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load the review queue.");
      setQueue([]);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  function handled(updated: IncidentResponse) {
    setDone((d) => [updated, ...d]);
    setQueue((q) => (q ?? []).filter((i) => i.incident_id !== updated.incident_id));
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Review queue</h1>
          <p>
            Cases the agent would not act on alone: evidence below the confidence threshold, or an action above the
            $500 autonomous limit. Each one is a paused LangGraph run that resumes when you decide.
          </p>
        </div>
        <button className="btn" onClick={load}>
          Refresh
        </button>
      </div>

      <ErrorNote error={error} />

      {queue === null ? (
        <div className="empty">Loading…</div>
      ) : queue.length === 0 ? (
        <div className="card empty">Nothing waiting for review.</div>
      ) : (
        <div className="grid grid-2">
          {queue.map((inc) => {
            const a = assessmentOf(inc);
            return (
              <section key={inc.incident_id} className="card">
                <div className="source-head">
                  <Link href={`/incidents/${inc.incident_id}`}>
                    <strong>{inc.incident?.subject ?? inc.incident_id}</strong>
                  </Link>
                  <span className="hint mono">{inc.incident?.customer_id}</span>
                </div>
                <div className="callout callout-warn" style={{ marginTop: 8 }}>
                  {reviewReason(inc)}
                </div>
                <dl className="kv" style={{ marginBottom: 12 }}>
                  <dt>Category</dt>
                  <dd>{humanize(inc.classification?.category)}</dd>
                  <dt>Confidence</dt>
                  <dd>{formatPercent(a?.confidence)}</dd>
                  {inc.order_amount_usd != null && (
                    <>
                      <dt>Order value</dt>
                      <dd>${inc.order_amount_usd.toFixed(2)}</dd>
                    </>
                  )}
                </dl>
                <ReviewPanel incident={inc} onDone={handled} compact />
              </section>
            );
          })}
        </div>
      )}

      {done.length > 0 && (
        <section className="card" style={{ marginTop: 16 }}>
          <h2>Reviewed this session</h2>
          <ul className="claims">
            {done.map((d) => (
              <li key={d.incident_id}>
                <StatusBadge status={d.status} />{" "}
                <Link href={`/incidents/${d.incident_id}`}>{d.incident?.subject ?? d.incident_id}</Link>
                <span className="hint"> · {humanize(d.decision?.action)}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </>
  );
}
