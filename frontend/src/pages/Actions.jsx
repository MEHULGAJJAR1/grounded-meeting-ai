import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  ChevronLeft,
  ChevronRight,
  ListTodo,
  Plus,
  Search,
  SlidersHorizontal,
} from "lucide-react";
import { useDebounce, useResource } from "../hooks/useResource";
import { useAuth } from "../context/AuthContext";
import { FILTERS, localDate, PRIORITIES, STATUSES } from "../services/format";
import {
  Button,
  EmptyState,
  ErrorState,
  PageHeading,
  Skeleton,
} from "../components/UI";
import ActionModal from "../components/ActionModal";
import ActionTable from "../components/ActionTable";

export default function Actions() {
  const [params, setParams] = useSearchParams();
  const { user } = useAuth();
  const [query, setQuery] = useState(params.get("q") || "");
  const debounced = useDebounce(query);
  const [priority, setPriority] = useState("");
  const [offset, setOffset] = useState(0);
  const [creating, setCreating] = useState(false);
  const filter = FILTERS.includes(params.get("filter"))
    ? params.get("filter")
    : "All";
  const status = params.get("status") || "";
  const resource = useResource(
    `/action-items?limit=25&offset=${offset}&filter=${encodeURIComponent(filter)}&q=${encodeURIComponent(debounced)}${priority ? `&priority=${priority}` : ""}${status ? `&status=${encodeURIComponent(status)}` : ""}`,
  );
  const total = resource.data?.total || 0;
  const items = resource.data?.items || [];
  function selectFilter(value) {
    setParams(value === "All" ? {} : { filter: value });
    setOffset(0);
  }
  return (
    <div className="page">
      <PageHeading
        eyebrow="FROM COMMITMENT TO COMPLETION"
        title="Action tracker"
        description="Real tasks. Clear ownership. Follow-through you can see."
      >
        <Button icon={Plus} onClick={() => setCreating(true)}>
          Create action
        </Button>
      </PageHeading>
      <div className="filter-pills" role="group" aria-label="Action filters">
        {FILTERS.map((value) => (
          <button
            key={value}
            className={filter === value ? "active" : ""}
            onClick={() => selectFilter(value)}
            aria-pressed={filter === value}
          >
            {value}
          </button>
        ))}
      </div>
      <div className="toolbar">
        <div className="input-icon search-input">
          <Search size={17} />
          <input
            aria-label="Search action items"
            placeholder="Find an action item…"
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setOffset(0);
            }}
          />
        </div>
        <select
          aria-label="Filter priority"
          value={priority}
          onChange={(event) => {
            setPriority(event.target.value);
            setOffset(0);
          }}
        >
          <option value="">All priorities</option>
          {PRIORITIES.map((p) => (
            <option key={p}>{p}</option>
          ))}
        </select>
        <select
          aria-label="Filter status"
          value={status}
          onChange={(event) => {
            const next = new URLSearchParams(params);
            if (event.target.value) next.set("status", event.target.value);
            else next.delete("status");
            setParams(next);
            setOffset(0);
          }}
        >
          <option value="">All statuses</option>
          {STATUSES.map((s) => (
            <option key={s}>{s}</option>
          ))}
        </select>
      </div>
      <div className="results-heading">
        <span>
          {resource.loading
            ? "Loading actions…"
            : `${total} action item${total !== 1 ? "s" : ""}`}
        </span>
        <span>Calendar deadlines first · {user.timezone}</span>
      </div>
      {resource.error ? (
        <ErrorState message={resource.error} onRetry={resource.reload} />
      ) : resource.loading ? (
        <Skeleton height={350} />
      ) : !items.length ? (
        <div className="card">
          <EmptyState
            icon={ListTodo}
            title="No actions in this view."
            description="Adjust your filters, create a task or process a meeting to extract the next steps."
          >
            <Button icon={Plus} onClick={() => setCreating(true)}>
              Create action
            </Button>
            <Button
              variant="secondary"
              onClick={() => {
                setParams({});
                setPriority("");
                setQuery("");
                setOffset(0);
              }}
            >
              Reset filters
            </Button>
          </EmptyState>
        </div>
      ) : (
        <div className="card action-card">
          <ActionTable
            items={items}
            today={localDate(user.timezone)}
            reload={resource.reload}
          />
        </div>
      )}
      {total > 25 && (
        <div className="pagination">
          <span>
            {offset + 1}–{Math.min(offset + 25, total)} of {total}
          </span>
          <Button
            variant="secondary"
            icon={ChevronLeft}
            disabled={!offset}
            onClick={() => setOffset(offset - 25)}
          >
            Previous
          </Button>
          <Button
            variant="secondary"
            disabled={offset + 25 >= total}
            onClick={() => setOffset(offset + 25)}
          >
            Next <ChevronRight size={15} />
          </Button>
        </div>
      )}
      <div className="action-footnote">
        <SlidersHorizontal size={14} />
        <p>
          Owners and literal deadlines extracted from transcripts are never
          guessed. Manual edits are explicitly labelled. Priority and status use
          application defaults when not stated.
        </p>
      </div>
      {creating && (
        <ActionModal
          onClose={() => setCreating(false)}
          onSaved={resource.reload}
        />
      )}
    </div>
  );
}
