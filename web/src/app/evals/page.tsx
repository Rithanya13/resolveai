"use client";

import { useState } from "react";
import { ErrorNote } from "@/components/ErrorNote";
import { api, ApiError } from "@/lib/api";
import { formatPercent, humanize } from "@/lib/format";
import type { EvalReport } from "@/lib/types";

const METRICS: { key: keyof EvalReport["metrics"]; label: string; help: string }[] = [
  { key: "category_accuracy", label: "Category accuracy", help: "Classifier picked the labeled category." },
  { key: "outcome_accuracy", label: "Outcome accuracy", help: "Auto-resolve vs. human review matched the label." },
  { key: "escalation_precision", label: "Escalation precision", help: "Of escalated cases, share that should have been." },
  { key: "escalation_recall", label: "Escalation recall", help: "Of cases needing a person, share the agent caught." },
  { key: "groundedness_rate", label: "Groundedness", help: "Auto-resolved cases that cited at least one source." },
];

export default function EvalsPage() {
  const [report, setReport] = useState<EvalReport | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setRunning(true);
    setError(null);
    try {
      setReport(await api.runEvals());
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Eval run failed.");
    } finally {
      setRunning(false);
    }
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Evals</h1>
          <p>
            Runs the labeled regression set in <code>evals/dataset.jsonl</code> through a fresh copy of the graph. The
            same harness runs in CI on every push, so a routing regression fails the build.
          </p>
        </div>
        <button className="btn btn-primary" onClick={run} disabled={running}>
          {running ? "Running…" : report ? "Run again" : "Run eval suite"}
        </button>
      </div>

      <ErrorNote error={error} />

      {!report ? (
        <div className="card empty">Run the suite to see accuracy, escalation precision/recall and groundedness.</div>
      ) : (
        <div className="stack">
          <div className="stats">
            {METRICS.map((m) => {
              const v = report.metrics[m.key];
              return (
                <div key={m.key} className="card stat">
                  <span className="stat-value" style={{ color: v >= 0.9 ? "var(--ok)" : v >= 0.7 ? "var(--warn)" : "var(--bad)" }}>
                    {formatPercent(v)}
                  </span>
                  <span>{m.label}</span>
                  <span className="stat-label">{m.help}</span>
                </div>
              );
            })}
          </div>

          <section className="card">
            <h2>Per-case results ({report.cases})</h2>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Case</th>
                    <th>Expected category</th>
                    <th>Actual</th>
                    <th>Expected outcome</th>
                    <th>Actual</th>
                    <th>Grounded</th>
                  </tr>
                </thead>
                <tbody>
                  {report.results.map((r) => {
                    const catOk = r.actual_category === r.expected_category;
                    const outOk = r.actual_outcome === r.expected_outcome;
                    return (
                      <tr key={r.case_id}>
                        <td className="mono">{r.case_id}</td>
                        <td>{humanize(r.expected_category)}</td>
                        <td>
                          <span className={`badge ${catOk ? "badge-ok" : "badge-bad"}`}>{humanize(r.actual_category)}</span>
                        </td>
                        <td>{humanize(r.expected_outcome)}</td>
                        <td>
                          <span className={`badge ${outOk ? "badge-ok" : "badge-bad"}`}>{humanize(r.actual_outcome)}</span>
                        </td>
                        <td>{r.actual_outcome === "auto_resolved" ? (r.grounded ? "Yes" : "No") : <span className="muted">n/a</span>}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>
        </div>
      )}
    </>
  );
}
