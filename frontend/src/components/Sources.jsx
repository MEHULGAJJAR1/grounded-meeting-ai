import { useState } from "react";
import { Link } from "react-router-dom";
import { ArrowUpRight, ChevronDown, FileText, Quote } from "lucide-react";
import { dateLabel } from "../services/format";

export default function Sources({ sources, claims = [], collapsed = true }) {
  const [open, setOpen] = useState(!collapsed);
  if (!sources.length) return null;
  return (
    <div className="answer-sources">
      <button
        className="sources-toggle"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
      >
        <FileText size={14} />
        {sources.length} retrieved {sources.length === 1 ? "source" : "sources"}
        <ChevronDown size={14} className={open ? "rotate" : ""} />
      </button>
      {open && (
        <div className="source-grid">
          {sources.map((source, index) => {
            const quotes = claims
              .filter((claim) => claim.source_ids.includes(source.id))
              .flatMap((claim) => claim.evidence_quotes)
              .filter((quote) => source.text.includes(quote));
            return (
              <div className="answer-source" key={source.id}>
                <span className="source-index">{index + 1}</span>
                <div>
                  <Link
                    to={`/meetings/${source.meeting_id}?line=${source.evidence[0]?.line_start || 1}`}
                  >
                    {source.meeting_title}
                    <ArrowUpRight size={13} />
                  </Link>
                  <span className="source-meta">
                    {dateLabel(source.meeting_date)} · {source.source_kind}
                    {source.evidence[0]?.filename &&
                      ` · ${source.evidence[0].filename}`}
                    {source.evidence[0]?.page &&
                      ` · page ${source.evidence[0].page}`}
                  </span>
                  <blockquote>
                    <Quote size={12} />
                    {(quotes[0] || source.text).slice(0, 600)}
                    {(quotes[0] || source.text).length > 600 && "…"}
                  </blockquote>
                  {source.record_provenance && (
                    <small>{source.record_provenance}</small>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
