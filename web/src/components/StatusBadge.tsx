import { STATUS_LABEL } from "@/lib/format";
import type { IncidentStatus } from "@/lib/types";

const TONE: Record<IncidentStatus, string> = {
  resolved: "badge-ok",
  pending_human_review: "badge-warn",
  escalated: "badge-bad",
  error: "badge-bad",
  unknown: "badge-muted",
};

export function StatusBadge({ status }: { status: IncidentStatus }) {
  return <span className={`badge ${TONE[status] ?? "badge-muted"}`}>{STATUS_LABEL[status] ?? status}</span>;
}
