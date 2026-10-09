import type {
  ApprovalRequest,
  EvalReport,
  IncidentResponse,
  SubmitIncidentRequest,
} from "./types";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
      cache: "no-store",
    });
  } catch {
    throw new ApiError(0, `Can't reach the ResolveAI API at ${API_URL}. Is the backend running?`);
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      // non-JSON error body; keep statusText
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

export const api = {
  listIncidents: () => request<{ incidents: IncidentResponse[] }>("/incidents").then((r) => r.incidents),
  getIncident: (id: string) => request<IncidentResponse>(`/incidents/${encodeURIComponent(id)}`),
  submitIncident: (body: SubmitIncidentRequest) =>
    request<IncidentResponse>("/incidents", { method: "POST", body: JSON.stringify(body) }),
  reviewIncident: (id: string, body: ApprovalRequest) =>
    request<IncidentResponse>(`/incidents/${encodeURIComponent(id)}/approve`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  runEvals: () => request<EvalReport>("/evals"),
};
