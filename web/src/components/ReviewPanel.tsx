"use client";

import { useState } from "react";
import { api, ApiError } from "@/lib/api";
import { humanize } from "@/lib/format";
import type { IncidentResponse, ResolutionAction } from "@/lib/types";
import { ErrorNote } from "./ErrorNote";

const ACTIONS: ResolutionAction[] = [
  "issue_refund",
  "resend_order",
  "reset_account_access",
  "correct_billing",
  "no_action_needed",
];

/**
 * Human-in-the-loop decision. Approving or rejecting resumes the paused
 * LangGraph run via POST /incidents/{id}/approve (Command(resume=...)).
 * When the agent had no proposal (low confidence), the reviewer picks the action.
 */
export function ReviewPanel({
  incident,
  onDone,
  compact = false,
}: {
  incident: IncidentResponse;
  onDone: (updated: IncidentResponse) => void;
  compact?: boolean;
}) {
  const pending = incident.pending_review;
  const hasProposal = Boolean(pending?.recommended_action);
  const [note, setNote] = useState("");
  const [action, setAction] = useState<ResolutionAction>("no_action_needed");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(approved: boolean) {
    setBusy(true);
    setError(null);
    try {
      const updated = await api.reviewIncident(incident.incident_id, {
        approved,
        note,
        ...(approved && !hasProposal ? { action, customer_message: message || undefined } : {}),
      });
      onDone(updated);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Review failed.");
    } finally {
      setBusy(false);
    }
  }

  if (!pending) return null;

  return (
    <div>
      {!compact && <div className="callout callout-warn">{pending.reason}</div>}
      {hasProposal ? (
        <div className="field">
          <label>Agent&apos;s proposed action</label>
          <div>
            <strong>{humanize(pending.recommended_action)}</strong>
          </div>
          {pending.proposed_customer_message && !compact && (
            <blockquote className="quote" style={{ marginTop: 8 }}>
              {pending.proposed_customer_message}
            </blockquote>
          )}
        </div>
      ) : (
        <>
          <div className="field">
            <label htmlFor={`action-${incident.incident_id}`}>Action to take</label>
            <select
              id={`action-${incident.incident_id}`}
              value={action}
              onChange={(e) => setAction(e.target.value as ResolutionAction)}
            >
              {ACTIONS.map((a) => (
                <option key={a} value={a}>
                  {humanize(a)}
                </option>
              ))}
            </select>
            <div className="hint">The agent had no confident proposal, so you choose.</div>
          </div>
          {!compact && (
            <div className="field">
              <label htmlFor={`msg-${incident.incident_id}`}>Message to customer (optional)</label>
              <textarea id={`msg-${incident.incident_id}`} value={message} onChange={(e) => setMessage(e.target.value)} />
            </div>
          )}
        </>
      )}
      <div className="field">
        <label htmlFor={`note-${incident.incident_id}`}>Reviewer note</label>
        <input
          id={`note-${incident.incident_id}`}
          value={note}
          placeholder="e.g. confirmed with finance"
          onChange={(e) => setNote(e.target.value)}
        />
        <div className="hint">Saved with the decision for the audit trail.</div>
      </div>
      <ErrorNote error={error} />
      <div className="btn-row">
        <button className="btn btn-ok" disabled={busy} onClick={() => submit(true)}>
          Approve
        </button>
        <button className="btn btn-bad" disabled={busy} onClick={() => submit(false)}>
          Reject
        </button>
      </div>
    </div>
  );
}
