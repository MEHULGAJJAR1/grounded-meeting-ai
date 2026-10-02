import { useState } from "react";
import { AlertCircle, ShieldCheck } from "lucide-react";
import { Badge, Button } from "./UI";
import { Evidence } from "./Evidence";

export default function GroundingPanel({ report, onLocate }) {
  const [filter, setFilter] = useState("issues");
  const [limit, setLimit] = useState(12);
  if (!report)
    return <p className="muted">No grounding report is available yet.</p>;
  const combined = [
    ...report.entries,
    ...report.corrections.map((c, i) => ({
      ...c,
      id: `correction-${i}`,
      evidence: [],
      metadata: true,
    })),
  ];
  const visible = combined.filter(
    (entry) =>
      filter === "all" ||
      (filter === "issues" && entry.verdict !== "supported") ||
      (filter === "supported" && entry.verdict === "supported"),
  );
  return (
    <div className="grounding-panel">
      <div className="grounding-intro">
        <span className="grounding-seal">
          <ShieldCheck size={29} />
        </span>
        <div>
          <h3>Confidence should come with context.</h3>
          <p>{report.verification_method}</p>
        </div>
        <div className="evidence-rate">
          <strong>{report.evidence_pass_rate}%</strong>
          <span>evidence pass rate</span>
        </div>
      </div>
      <div className="grounding-stats">
        <div>
          <span className="legend-dot" style={{ background: "#258469" }} />
          <strong>{report.verified}</strong>
          <span>Verified claims</span>
        </div>
        <div>
          <span className="legend-dot" style={{ background: "#e0aa57" }} />
          <strong>{report.review}</strong>
          <span>Need review</span>
        </div>
        <div>
          <span className="legend-dot" style={{ background: "#dd786e" }} />
          <strong>{report.flagged}</strong>
          <span>Withheld claims</span>
        </div>
        <div>
          <span className="legend-dot" style={{ background: "#9380c8" }} />
          <strong>{report.metadata_corrections}</strong>
          <span>Metadata corrections</span>
        </div>
      </div>
      <div className="grounding-caveat">
        <AlertCircle size={16} />
        <p>
          {report.confidence_method} Verification reduces unsupported output; it
          does not guarantee zero hallucinations. Withheld proposals below are
          not presented as meeting facts.
        </p>
      </div>
      <div className="tabs compact-tabs">
        {[
          ["issues", "Review & corrections"],
          ["supported", "Verified"],
          ["all", "All checks"],
        ].map(([key, title]) => (
          <button
            className={filter === key ? "active" : ""}
            key={key}
            onClick={() => {
              setFilter(key);
              setLimit(12);
            }}
          >
            {title}
          </button>
        ))}
      </div>
      {!visible.length ? (
        <div className="grounding-clear">
          <ShieldCheck size={22} />
          <span>
            No issues in this view. The original evidence remains available for
            your review.
          </span>
        </div>
      ) : (
        <div className="grounding-entries">
          {visible.slice(0, limit).map((entry) => (
            <div className={`grounding-entry ${entry.verdict}`} key={entry.id}>
              <div className="grounding-entry-top">
                <Badge value={entry.verdict}>
                  {entry.metadata
                    ? "Metadata correction"
                    : entry.verdict === "unsupported"
                      ? "Withheld · not fact"
                      : entry.verdict === "uncertain"
                        ? "Needs review"
                        : "Verified"}
                </Badge>
                <span className="entry-kind">
                  {entry.kind.replaceAll("_", " ")}
                </span>
              </div>
              <p>{entry.text}</p>
              {entry.metadata && (
                <div className="correction-values">
                  <code>
                    {entry.field}: {entry.original_value}
                  </code>
                  <span>→</span>
                  <code>{entry.fallback}</code>
                </div>
              )}
              <small>{entry.reason}</small>
              <Evidence evidence={entry.evidence} onLocate={onLocate} />
            </div>
          ))}
          {visible.length > limit && (
            <Button variant="secondary" onClick={() => setLimit(limit + 20)}>
              Show more checks ({visible.length - limit} remaining)
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
