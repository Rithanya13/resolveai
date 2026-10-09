import { Fragment } from "react";

/** The real path the LangGraph run took, plus the human_review node it is parked on (if paused). */
export function TracePipeline({ trace, paused }: { trace: string[]; paused: boolean }) {
  const steps = paused ? [...trace, "human_review"] : trace;
  return (
    <div className="pipeline" aria-label="Graph execution trace">
      {steps.map((step, i) => {
        const isPause = paused && i === steps.length - 1;
        return (
          <Fragment key={`${step}-${i}`}>
            {i > 0 && <span className="step-arrow">→</span>}
            <span className={`step ${isPause ? "paused" : "done"}`}>
              {step}
              {isPause ? " (paused)" : ""}
            </span>
          </Fragment>
        );
      })}
    </div>
  );
}
