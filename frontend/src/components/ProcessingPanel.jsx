import { Check, LoaderCircle, ShieldCheck } from "lucide-react";

const STAGES = [
  ["Preprocessing", 5],
  ["Chunking", 12],
  ["Embeddings", 20],
  ["AI analysis", 30],
  ["Structured output", 58],
  ["Grounding", 62],
  ["Saving", 90],
  ["Complete", 100],
];
export default function ProcessingPanel({ meeting }) {
  return (
    <div className="card processing-panel" role="status" aria-live="polite">
      <div className="processing-panel-title">
        <span className="processing-icon">
          <ShieldCheck size={22} />
        </span>
        <div>
          <h3>Turning conversation into clarity</h3>
          <p>{meeting.processing_stage}</p>
        </div>
        <span className="processing-percent">
          {meeting.processing_progress}%
        </span>
      </div>
      <div className="processing-track">
        <div style={{ width: `${meeting.processing_progress}%` }} />
      </div>
      <div className="processing-stages">
        {STAGES.map(([label, threshold], index) => {
          const reached = meeting.processing_progress >= threshold;
          const current =
            reached &&
            (index === STAGES.length - 1 ||
              meeting.processing_progress < STAGES[index + 1][1]);
          return (
            <div
              className={`${reached ? "reached" : ""} ${current ? "current" : ""}`}
              key={label}
            >
              <span>
                {reached && !current ? (
                  <Check size={12} />
                ) : current ? (
                  <LoaderCircle size={12} className="spin" />
                ) : (
                  index + 1
                )}
              </span>
              {label}
            </div>
          );
        })}
      </div>
      <small>
        Progress comes from completed server phases and chunks. It is not a
        timer or an estimate.
      </small>
    </div>
  );
}
