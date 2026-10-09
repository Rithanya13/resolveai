import type { RetrievedPassage, ToolEvidence } from "@/lib/types";

export function sourceAnchor(id: string) {
  return `src-${id.replace(/[^a-zA-Z0-9_-]/g, "-")}`;
}

/** Every retrieved policy passage and MCP tool result the agent saw -- the targets citations point at. */
export function Sources({
  passages,
  evidence,
  highlight,
}: {
  passages: RetrievedPassage[];
  evidence: ToolEvidence[];
  highlight: string | null;
}) {
  const toolGroups = Array.from(new Set(evidence.map((e) => e.source_tool)));
  return (
    <div className="stack">
      <div>
        <h3>Tool evidence (MCP)</h3>
        <div className="hint" style={{ marginBottom: 8 }}>
          Live CRM and ticketing lookups. Only confirmed records count toward confidence.
        </div>
        {toolGroups.length === 0 && <div className="muted">No tool calls.</div>}
        {toolGroups.map((tool) => (
          <div key={tool} id={sourceAnchor(tool)} className={`source ${highlight === tool ? "highlight" : ""}`}>
            <div className="source-head">
              <code>{tool}</code>
            </div>
            {evidence
              .filter((e) => e.source_tool === tool)
              .map((e, i) => (
                <div key={i}>
                  <p>{e.summary}</p>
                  {e.raw?.found === false && <span className="badge badge-bad">no record found</span>}
                  <details>
                    <summary>Raw result</summary>
                    <pre>{JSON.stringify(e.raw, null, 2)}</pre>
                  </details>
                </div>
              ))}
          </div>
        ))}
      </div>
      <div>
        <h3>Retrieved policy (hybrid RAG)</h3>
        <div className="hint" style={{ marginBottom: 8 }}>
          BM25 + vector search, fused with Reciprocal Rank Fusion.
        </div>
        {passages.length === 0 && <div className="muted">No passages retrieved.</div>}
        {passages.map((p) => (
          <div key={p.doc_id} id={sourceAnchor(p.doc_id)} className={`source ${highlight === p.doc_id ? "highlight" : ""}`}>
            <div className="source-head">
              <strong>{p.title}</strong>
              <code className="muted">{p.doc_id}</code>
            </div>
            <p>{p.text}</p>
            <div className="hint">RRF score {p.score.toFixed(4)}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

