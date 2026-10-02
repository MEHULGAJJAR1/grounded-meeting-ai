import { Copy, MessageSquareText } from "lucide-react";
import { Badge, SupportBadge } from "../UI";
import { ClaimList, Evidence } from "../Evidence";
export function SummaryBody({
  summaryTab,
  setSummaryTab,
  copy,
  summary,
  meeting,
  locate,
}) {
  return (
    <>
      <div className="summary-toolbar">
        <div className="tabs compact-tabs">
          {[
            ["three_line_summary", "3-line"],
            ["executive_summary", "Executive"],
            ["detailed_summary", "Detailed"],
            ["bullet_summary", "Bullet"],
          ].map(([value, label]) => (
            <button
              className={summaryTab === value ? "active" : ""}
              onClick={() => setSummaryTab(value)}
              key={value}
            >
              {label}
            </button>
          ))}
        </div>
        <button
          className="text-btn"
          onClick={() =>
            copy(summary[summaryTab].map((s) => s.text).join("\n"))
          }
        >
          <Copy size={14} />
          Copy
        </button>
      </div>
      {meeting.analysis_provider === "Local extractive" && (
        <p className="extractive-note">
          Local mode · summaries are selected, source-faithful excerpts, not LLM
          synthesis.
        </p>
      )}
      <ClaimList items={summary[summaryTab]} onLocate={locate} />
      {summary.sentiment && (
        <div className="tone-overview">
          <MessageSquareText size={17} />
          <div>
            <span className="eyebrow">DESCRIPTIVE TONE OVERVIEW</span>
            <p>
              <strong>{summary.sentiment.label}</strong> ·{" "}
              {summary.sentiment.description}
            </p>
            <Evidence evidence={summary.sentiment.evidence} onLocate={locate} />
          </div>
        </div>
      )}
    </>
  );
}

export function DecisionsBody({
  decisionTab,
  setDecisionTab,
  decisions,
  locate,
}) {
  return (
    <>
      <div className="tabs compact-tabs">
        {["All", "Confirmed", "Tentative", "Rejected"].map((kind) => (
          <button
            className={decisionTab === kind ? "active" : ""}
            onClick={() => setDecisionTab(kind)}
            key={kind}
          >
            {kind}
          </button>
        ))}
      </div>
      {!decisions.length ? (
        <p className="muted empty-line">No decisions in this category.</p>
      ) : (
        <div className="intelligence-list">
          {decisions.map((d) => (
            <article key={d.id}>
              <Badge value={d.decision_type} />
              <p>{d.text}</p>
              <div className="claim-meta">
                <SupportBadge item={d} />
                <Evidence evidence={d.evidence} onLocate={locate} />
              </div>
            </article>
          ))}
        </div>
      )}
    </>
  );
}
