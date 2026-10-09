"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { ErrorNote } from "@/components/ErrorNote";
import { StatusBadge } from "@/components/StatusBadge";
import { api, ApiError } from "@/lib/api";
import { assessmentOf, formatPercent, humanize } from "@/lib/format";
import type { IncidentResponse, SubmitIncidentRequest } from "@/lib/types";

// The mock CRM in `src/resolveai/tools/mock_data.py` -- each preset exercises a different graph path.
const PRESETS: { label: string; body: SubmitIncidentRequest }[] = [
  {
    label: "Duplicate charge (auto-resolves)",
    body: {
      customer_id: "cust_1002",
      subject: "Charged twice for one order",
      description: "I was charged twice for order_5002, please refund the duplicate charge.",
    },
  },
  {
    label: "$899 refund (needs approval)",
    body: {
      customer_id: "cust_1004",
      subject: "High value order never arrived, need a refund",
      description: "This order never arrived per tracking and I need a refund immediately, it's been over a week.",
    },
  },
  {
    label: "Unknown customer (low confidence)",
    body: {
      customer_id: "cust_9999",
      subject: "Locked out of my account",
      description: "I can't log in to my account after too many attempts.",
    },
  },
];

export default function IncidentsPage() {
  const [incidents, setIncidents] = useState<IncidentResponse[] | null>(null);
  const [form, setForm] = useState<SubmitIncidentRequest>(PRESETS[0].body);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [last, setLast] = useState<IncidentResponse | null>(null);

  const load = useCallback(async () => {
    try {
      const list = await api.listIncidents();
      setIncidents([...list].reverse());
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load incidents.");
      setIncidents([]);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const created = await api.submitIncident(form);
      setLast(created);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Submit failed.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Incidents</h1>
          <p>
            Each incident runs through the agent graph: classify, retrieve policy, pull CRM and ticketing evidence over
            MCP, assess confidence, then resolve or hand off to a person.
          </p>
        </div>
      </div>

      <ErrorNote error={error} />

      <div className="grid grid-main">
        <section className="card">
          <h2>Recent incidents</h2>
          {incidents === null ? (
            <div className="empty">Loading…</div>
          ) : incidents.length === 0 ? (
            <div className="empty">No incidents yet. Submit one to see the agent work.</div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Incident</th>
                    <th>Category</th>
                    <th>Confidence</th>
                    <th>Action</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {incidents.map((inc) => {
                    const a = assessmentOf(inc);
                    return (
                      <tr key={inc.incident_id}>
                        <td>
                          <Link href={`/incidents/${inc.incident_id}`}>
                            {inc.incident?.subject ?? inc.incident_id}
                          </Link>
                          <div className="hint mono">
                            {inc.incident_id} · {inc.incident?.customer_id}
                          </div>
                        </td>
                        <td>{humanize(inc.classification?.category)}</td>
                        <td>{formatPercent(a?.confidence)}</td>
                        <td>{humanize(inc.decision?.action ?? inc.pending_review?.recommended_action)}</td>
                        <td>
                          <StatusBadge status={inc.status} />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <section className="card">
          <h2>Submit an incident</h2>
          <div className="btn-row" style={{ marginBottom: 12 }}>
            {PRESETS.map((p) => (
              <button key={p.label} type="button" className="btn" onClick={() => setForm(p.body)}>
                {p.label}
              </button>
            ))}
          </div>
          <form onSubmit={submit}>
            <div className="field">
              <label htmlFor="customer_id">Customer ID</label>
              <input
                id="customer_id"
                className="mono"
                value={form.customer_id}
                onChange={(e) => setForm({ ...form, customer_id: e.target.value })}
                required
              />
              <div className="hint">Mock CRM customers: cust_1001 to cust_1004.</div>
            </div>
            <div className="field">
              <label htmlFor="subject">Subject</label>
              <input id="subject" value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })} required />
            </div>
            <div className="field">
              <label htmlFor="description">Description</label>
              <textarea
                id="description"
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                required
              />
            </div>
            <button className="btn btn-primary" disabled={submitting} type="submit">
              {submitting ? "Agent is investigating…" : "Run agent"}
            </button>
          </form>
          {last && (
            <div className={`callout ${last.status === "resolved" ? "callout-ok" : "callout-warn"}`} style={{ marginTop: 12 }}>
              <StatusBadge status={last.status} />{" "}
              <Link href={`/incidents/${last.incident_id}`}>Open {last.incident_id}</Link>
            </div>
          )}
        </section>
      </div>
    </>
  );
}
