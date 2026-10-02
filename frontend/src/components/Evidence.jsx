import { useState } from "react";
import { ArrowUpRight, Quote, ChevronDown } from "lucide-react";
import { Link } from "react-router-dom";
import { SupportBadge } from "./UI";

export function Evidence({ evidence = [], onLocate, meetingId }) {
  const [expanded, setExpanded] = useState(false);
  if (!evidence.length) return null;
  return (
    <div className="evidence">
      <button
        className="evidence-trigger"
        onClick={() => setExpanded(!expanded)}
        aria-expanded={expanded}
      >
        <Quote size={13} />
        {evidence.length} source {evidence.length === 1 ? "quote" : "quotes"}
        <ChevronDown size={13} className={expanded ? "rotate" : ""} />
      </button>
      {expanded && (
        <div className="evidence-quotes">
          {evidence.map((item, index) => (
            <div className="evidence-quote" key={index}>
              <blockquote>{item.quote}</blockquote>
              <div className="evidence-footer">
                <span>
                  Lines {item.line_start}–{item.line_end}
                  {item.page && ` · page ${item.page}`}
                  {item.section && ` · section ${item.section}`}
                  {item.filename && ` · ${item.filename}`}
                </span>
                {onLocate ? (
                  <button onClick={() => onLocate(item)} className="text-btn">
                    View in transcript <ArrowUpRight size={13} />
                  </button>
                ) : meetingId ? (
                  <Link
                    className="text-btn"
                    to={`/meetings/${meetingId}?line=${item.line_start}`}
                  >
                    View source <ArrowUpRight size={13} />
                  </Link>
                ) : null}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
export function ClaimList({
  items = [],
  onLocate,
  meetingId,
  empty = "No supported claims were extracted for this section.",
}) {
  if (!items.length) return <p className="muted empty-line">{empty}</p>;
  return (
    <div className="claim-list">
      {items.map((item, index) => (
        <article
          className={`claim-item ${item.grounding_status === "review" ? "claim-review" : ""}`}
          key={item.id || index}
        >
          <div className="claim-number">
            {String(index + 1).padStart(2, "0")}
          </div>
          <div className="claim-content">
            <p>{item.text}</p>
            <div className="claim-meta">
              <SupportBadge item={item} />
              <Evidence
                evidence={item.evidence}
                onLocate={onLocate}
                meetingId={meetingId}
              />
            </div>
          </div>
        </article>
      ))}
    </div>
  );
}
