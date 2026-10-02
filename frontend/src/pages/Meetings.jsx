import { useState } from "react";
import { Link } from "react-router-dom";
import {
  CalendarDays,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Grid2X2,
  List,
  ListTodo,
  Pencil,
  Plus,
  Search,
  Trash2,
} from "lucide-react";
import { useDebounce, useResource } from "../hooks/useResource";
import { useToast } from "../context/ToastContext";
import { api, errorMessage } from "../services/api";
import { dateLabel } from "../services/format";
import {
  AvatarGroup,
  Badge,
  Button,
  ConfirmDialog,
  EmptyState,
  ErrorState,
  PageHeading,
  Skeleton,
} from "../components/UI";

export default function Meetings() {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [view, setView] = useState("grid");
  const [offset, setOffset] = useState(0);
  const debounced = useDebounce(query);
  const toast = useToast();
  const resource = useResource(
    `/meetings?limit=12&offset=${offset}&q=${encodeURIComponent(debounced)}${status ? `&status=${status}` : ""}`,
  );
  const [deleting, setDeleting] = useState(null);
  const [busy, setBusy] = useState(false);
  const items = resource.data?.items || [];
  const total = resource.data?.total || 0;
  async function remove() {
    setBusy(true);
    try {
      await api.delete(`/meetings/${deleting.id}`);
      setDeleting(null);
      if (items.length === 1 && offset) setOffset(Math.max(0, offset - 12));
      else resource.reload();
      toast("Meeting and its associated records deleted.");
    } catch (error) {
      toast(errorMessage(error), "error");
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="page">
      <PageHeading
        eyebrow="CONVERSATIONS TO CLARITY"
        title="Your meetings"
        description="A searchable history of what was said, decided and promised."
      >
        <Link to="/meetings/new" className="btn btn-primary">
          <Plus size={17} />
          New meeting
        </Link>
      </PageHeading>
      <div className="toolbar">
        <div className="input-icon search-input">
          <Search size={17} />
          <input
            aria-label="Find meetings"
            placeholder="Find a meeting or project…"
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setOffset(0);
            }}
          />
        </div>
        <select
          aria-label="Meeting processing status"
          value={status}
          onChange={(event) => {
            setStatus(event.target.value);
            setOffset(0);
          }}
        >
          <option value="">All statuses</option>
          {["draft", "queued", "processing", "completed", "failed"].map(
            (item) => (
              <option key={item} value={item}>
                {item[0].toUpperCase() + item.slice(1)}
              </option>
            ),
          )}
        </select>
        <div className="view-switch">
          <button
            className={view === "grid" ? "active" : ""}
            aria-label="Grid view"
            aria-pressed={view === "grid"}
            onClick={() => setView("grid")}
          >
            <Grid2X2 size={17} />
          </button>
          <button
            className={view === "list" ? "active" : ""}
            aria-label="List view"
            aria-pressed={view === "list"}
            onClick={() => setView("list")}
          >
            <List size={17} />
          </button>
        </div>
      </div>
      <div className="results-heading">
        <span>
          {resource.loading
            ? "Loading meetings…"
            : `${total} meeting${total !== 1 ? "s" : ""}`}
        </span>
        <span>Most recent first</span>
      </div>
      {resource.error ? (
        <ErrorState message={resource.error} onRetry={resource.reload} />
      ) : resource.loading ? (
        <div className="meeting-grid">
          {[0, 1, 2, 3, 4, 5].map((i) => (
            <Skeleton height={270} key={i} />
          ))}
        </div>
      ) : !items.length ? (
        <div className="card">
          <EmptyState
            icon={CalendarDays}
            title={
              query || status
                ? "No meetings match your filters."
                : "Your next meeting starts here."
            }
            description="Create a meeting, add your transcript and turn the conversation into source-backed intelligence."
          >
            <Link to="/meetings/new" className="btn btn-primary">
              <Plus size={16} />
              Create a meeting
            </Link>
            {(query || status) && (
              <Button
                variant="secondary"
                onClick={() => {
                  setQuery("");
                  setStatus("");
                }}
              >
                Clear filters
              </Button>
            )}
          </EmptyState>
        </div>
      ) : view === "grid" ? (
        <div className="meeting-grid">
          {items.map((meeting, index) => (
            <article className="card meeting-card" key={meeting.id}>
              <div className="meeting-card-top">
                <span className={`meeting-tile color-${index % 4}`}>
                  <CalendarDays size={22} />
                </span>
                <Badge value={meeting.processing_status}>
                  {meeting.processing_status === "completed"
                    ? "Analysed"
                    : meeting.processing_status}
                </Badge>
              </div>
              <Link className="meeting-title" to={`/meetings/${meeting.id}`}>
                <h2>{meeting.title}</h2>
              </Link>
              <div className="meeting-card-meta">
                <span>{dateLabel(meeting.date, { year: "numeric" })}</span>
                <i />
                {meeting.project || meeting.meeting_type}
                {meeting.is_demo && (
                  <small className="sample-label">Sample</small>
                )}
              </div>
              <p className="meeting-preview">
                {meeting.preview ||
                  (meeting.processing_status === "draft"
                    ? "Your transcript is ready to become clear decisions and next steps."
                    : meeting.processing_status === "failed"
                      ? "Analysis needs attention. Open the meeting to review and retry."
                      : `Processing · ${meeting.processing_stage}`)}
              </p>
              {meeting.preview_grounding_status === "review" && (
                <Badge value="uncertain">Preview needs review</Badge>
              )}
              <div className="meeting-card-insights">
                <span>
                  <ListTodo size={14} />
                  {meeting.action_count} actions
                </span>
                <span>
                  <CheckCircle2 size={14} />
                  {meeting.decision_count} decisions
                </span>
              </div>
              <div className="meeting-card-footer">
                <AvatarGroup names={meeting.participants} />
                <div className="row-actions">
                  <Link
                    to={`/meetings/${meeting.id}/edit`}
                    className="icon-btn"
                    aria-label={`Edit ${meeting.title}`}
                  >
                    <Pencil size={15} />
                  </Link>
                  <button
                    className="icon-btn"
                    disabled={["processing", "queued"].includes(
                      meeting.processing_status,
                    )}
                    aria-label={`Delete ${meeting.title}`}
                    onClick={() => setDeleting(meeting)}
                  >
                    <Trash2 size={15} />
                  </button>
                  <Link to={`/meetings/${meeting.id}`} className="open-meeting">
                    Open <ChevronRight size={14} />
                  </Link>
                </div>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <div className="card table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th>Meeting</th>
                <th>Date</th>
                <th>Participants</th>
                <th>Actions</th>
                <th>Status</th>
                <th>Manage</th>
              </tr>
            </thead>
            <tbody>
              {items.map((meeting) => (
                <tr key={meeting.id}>
                  <td data-label="Meeting">
                    <Link
                      className="table-title"
                      to={`/meetings/${meeting.id}`}
                    >
                      {meeting.title}
                    </Link>
                    <small>
                      {meeting.project} · {meeting.meeting_type}
                    </small>
                  </td>
                  <td data-label="Date">
                    {dateLabel(meeting.date, { year: "numeric" })}
                  </td>
                  <td data-label="Participants">
                    <AvatarGroup names={meeting.participants} />
                  </td>
                  <td data-label="Actions">{meeting.action_count}</td>
                  <td data-label="Status">
                    <Badge value={meeting.processing_status} />
                  </td>
                  <td data-label="Manage">
                    <div className="row-actions">
                      <Link
                        to={`/meetings/${meeting.id}/edit`}
                        className="icon-btn"
                        aria-label={`Edit ${meeting.title}`}
                      >
                        <Pencil size={16} />
                      </Link>
                      <button
                        className="icon-btn"
                        onClick={() => setDeleting(meeting)}
                        disabled={["processing", "queued"].includes(
                          meeting.processing_status,
                        )}
                        aria-label={`Delete ${meeting.title}`}
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {total > 12 && (
        <div className="pagination">
          <span>
            {offset + 1}–{Math.min(offset + 12, total)} of {total}
          </span>
          <Button
            variant="secondary"
            disabled={!offset}
            icon={ChevronLeft}
            onClick={() => setOffset(offset - 12)}
          >
            Previous
          </Button>
          <Button
            variant="secondary"
            disabled={offset + 12 >= total}
            onClick={() => setOffset(offset + 12)}
          >
            Next <ChevronRight size={15} />
          </Button>
        </div>
      )}
      {deleting && (
        <ConfirmDialog
          title="Delete this meeting?"
          message="The transcript, summaries, documents, citations and action records associated with this meeting will be permanently deleted."
          onClose={() => !busy && setDeleting(null)}
          onConfirm={remove}
          busy={busy}
        />
      )}
    </div>
  );
}
