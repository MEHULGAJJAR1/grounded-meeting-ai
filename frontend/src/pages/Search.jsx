import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  ArrowRight,
  ArrowUpRight,
  ChevronDown,
  FileSearch,
  Search,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { useResource } from "../hooks/useResource";
import { useAuth } from "../context/AuthContext";
import { api, errorMessage } from "../services/api";
import { dateLabel } from "../services/format";
import {
  Badge,
  Button,
  EmptyState,
  ErrorState,
  PageHeading,
  Skeleton,
} from "../components/UI";

const EXAMPLES = [
  "Which meetings discussed deployment?",
  "Show all action items assigned to Rahul.",
  "Which decisions were made about the dashboard?",
  "What risks are still unresolved?",
  "Which tasks are overdue?",
];
export default function SearchPage() {
  const [params, setParams] = useSearchParams();
  const { configuration } = useAuth();
  const [query, setQuery] = useState(params.get("q") || "");
  const [scope, setScope] = useState("");
  const meetings = useResource("/meetings?limit=100");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState("all");
  const [expanded, setExpanded] = useState({});
  const lastQuery = useRef("");
  const pendingRequest = useRef(0);
  useEffect(() => {
    const q = params.get("q");
    if (q && q !== lastQuery.current) {
      setQuery(q);
      run(q, false);
    }
  }, [params.get("q")]);
  async function run(value = query, updateURL = true) {
    if (value.trim().length < 2) return;
    const current = ++pendingRequest.current;
    lastQuery.current = value;
    if (updateURL) setParams({ q: value });
    setLoading(true);
    setError("");
    setFilter("all");
    try {
      const { data } = await api.post("/search", {
        query: value,
        limit: 12,
        meeting_id: scope || null,
      });
      if (current === pendingRequest.current) setResult(data);
    } catch (failure) {
      if (current === pendingRequest.current) setError(errorMessage(failure));
    } finally {
      if (current === pendingRequest.current) setLoading(false);
    }
  }
  const sources = (result?.sources || []).filter(
    (source) => filter === "all" || source.source_kind.startsWith(filter),
  );
  return (
    <div className="page search-page">
      <PageHeading
        eyebrow="FIND THE THREAD"
        title="Search beyond keywords"
        description="Find the right conversation, decision or next step across your own history."
      />
      <div className="card semantic-search-card">
        <div className="semantic-search-icon">
          <Search size={24} />
        </div>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            run();
          }}
        >
          <div className="semantic-input">
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              required
              minLength={2}
              maxLength={2000}
              placeholder="What are you looking for in your meetings?"
              aria-label="Semantic search query"
            />
            <Button type="submit" icon={Search} busy={loading}>
              Search
            </Button>
          </div>
          <div className="search-options">
            <span>
              <ShieldCheck size={14} />
              Only your workspace
            </span>
            <select
              aria-label="Search meeting scope"
              value={scope}
              onChange={(event) => setScope(event.target.value)}
            >
              <option value="">All meetings</option>
              {meetings.data?.items.map((m) => (
                <option value={m.id} key={m.id}>
                  {m.title}
                </option>
              ))}
            </select>
            <span className="search-engine">
              <Sparkles size={13} />
              {configuration?.provider === "openai"
                ? "Semantic + record retrieval"
                : "Local lexical embeddings + records"}
            </span>
          </div>
        </form>
      </div>
      {error ? (
        <ErrorState message={error} onRetry={() => run()} />
      ) : loading ? (
        <div className="search-result-list">
          {[0, 1, 2].map((i) => (
            <Skeleton height={200} key={i} />
          ))}
        </div>
      ) : !result ? (
        <div className="search-intro">
          <div className="eyebrow">START WITH A QUESTION</div>
          <h2>There’s a meeting for that.</h2>
          <p>
            Look for a topic, a commitment or a decision. Your sources are
            always one click away.
          </p>
          <div className="search-examples">
            {EXAMPLES.map((example) => (
              <button
                key={example}
                onClick={() => {
                  setQuery(example);
                  run(example);
                }}
              >
                <FileSearch size={17} />
                <span>{example}</span>
                <ArrowUpRight size={15} />
              </button>
            ))}
          </div>
        </div>
      ) : (
        <>
          <div className="search-results-summary">
            <span>
              <strong>{result.sources.length}</strong> retrieved sources
            </span>
            <small>{result.retrieval_mode}</small>
            <Link
              to={`/assistant?q=${encodeURIComponent(query)}`}
              className="text-btn"
            >
              Ask the assistant <ArrowRight size={14} />
            </Link>
          </div>
          <div className="filter-pills">
            {[
              ["all", "All sources"],
              ["transcript", "Transcripts"],
              ["action", "Action items"],
              ["decision", "Decisions"],
              ["risk", "Risks"],
              ["question", "Questions"],
            ].map(([value, label]) => (
              <button
                className={filter === value ? "active" : ""}
                onClick={() => setFilter(value)}
                key={value}
              >
                {label}
              </button>
            ))}
          </div>
          {!sources.length ? (
            <div className="card">
              <EmptyState
                icon={Search}
                title="No supporting sources in this view."
                description="Try another question or process a relevant transcript so it can be indexed."
              />
            </div>
          ) : (
            <div className="search-result-list">
              {sources.map((source, index) => (
                <article className="card search-result" key={source.id}>
                  <div className="search-result-top">
                    <span className="source-index">{index + 1}</span>
                    <Badge value={source.source_kind}>
                      {source.source_kind}
                    </Badge>
                    <span
                      className="retrieval-score"
                      title="Retrieval rank score, not a calibrated confidence probability"
                    >
                      Match {source.score.toFixed(2)}
                    </span>
                  </div>
                  <Link
                    className="search-result-title"
                    to={`/meetings/${source.meeting_id}?line=${source.evidence[0]?.line_start || 1}`}
                  >
                    <h3>{source.meeting_title}</h3>
                    <ArrowUpRight size={17} />
                  </Link>
                  <div className="source-meta">
                    {dateLabel(source.meeting_date, { year: "numeric" })}
                    {source.evidence[0]?.line_start &&
                      ` · source lines ${source.evidence[0].line_start}–${source.evidence[0].line_end}`}
                  </div>
                  <pre className="search-result-excerpt">
                    {expanded[source.id]
                      ? source.text
                      : source.text.slice(0, 550)}
                    {!expanded[source.id] && source.text.length > 550
                      ? "…"
                      : ""}
                  </pre>
                  {source.record_provenance && (
                    <small className="source-record-provenance">
                      {source.record_provenance}
                    </small>
                  )}
                  <div className="search-result-footer">
                    <Link
                      className="text-btn"
                      to={`/meetings/${source.meeting_id}?line=${source.evidence[0]?.line_start || 1}`}
                    >
                      Open source meeting <ArrowRight size={14} />
                    </Link>
                    {source.text.length > 550 && (
                      <button
                        className="text-btn"
                        onClick={() =>
                          setExpanded((old) => ({
                            ...old,
                            [source.id]: !old[source.id],
                          }))
                        }
                      >
                        {expanded[source.id]
                          ? "Collapse quote"
                          : "Expand quote"}
                        <ChevronDown size={13} />
                      </button>
                    )}
                  </div>
                </article>
              ))}
            </div>
          )}
          <p className="search-note">{result.note}</p>
        </>
      )}
    </div>
  );
}
