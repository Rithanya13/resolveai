import { confidenceBand, formatPercent } from "@/lib/format";

export function ConfidenceMeter({ confidence, threshold }: { confidence: number; threshold: number }) {
  const band = confidenceBand(confidence, threshold);
  return (
    <div className="meter" role="img" aria-label={`Confidence ${formatPercent(confidence)}, threshold ${formatPercent(threshold)}`}>
      <div className="meter-track">
        <div className={`meter-fill ${band}`} style={{ width: `${Math.min(confidence, 1) * 100}%` }} />
        <div className="meter-threshold" style={{ left: `${threshold * 100}%` }} title="Auto-resolve threshold" />
      </div>
      <div className="meter-labels">
        <span>
          <strong style={{ color: "var(--text)" }}>{formatPercent(confidence)}</strong> confidence
        </span>
        <span>auto-resolve at {formatPercent(threshold)}</span>
      </div>
    </div>
  );
}
