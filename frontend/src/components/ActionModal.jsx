import { useState } from "react";
import { Save } from "lucide-react";
import { useResource } from "../hooks/useResource";
import { useToast } from "../context/ToastContext";
import { api, errorMessage } from "../services/api";
import { dependencyText, PRIORITIES, STATUSES } from "../services/format";
import { Button, Field, Modal, SupportBadge } from "./UI";
import { Evidence } from "./Evidence";

export default function ActionModal({ item, meetingId, onClose, onSaved }) {
  const toast = useToast();
  const meetings = useResource(
    !item && !meetingId ? "/meetings?limit=100" : null,
  );
  const [form, setForm] = useState({
    meeting_id: item?.meeting_id || meetingId || "",
    task: item?.task || "",
    owner: item?.owner || "Unassigned",
    due_date: item?.due_date || "",
    priority: item?.priority || "Medium",
    status: item?.status || "Pending",
    notes: item?.notes || "",
    dependencies: (item?.dependencies || []).map(dependencyText).join("\n"),
  });
  const [clearLiteral, setClearLiteral] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const set = (key, value) => setForm((old) => ({ ...old, [key]: value }));
  async function save(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const values = {
        ...form,
        owner: form.owner.trim() || "Unassigned",
        due_date: form.due_date || null,
        dependencies: form.dependencies
          .split("\n")
          .map((s) => s.trim())
          .filter(Boolean),
      };
      if (item) {
        const changed = {};
        for (const key of ["task", "owner", "priority", "status", "notes"])
          if (values[key] !== item[key]) changed[key] = values[key];
        if (
          (values.due_date || null) !== (item.due_date || null) ||
          clearLiteral
        )
          changed.due_date = values.due_date;
        if (
          form.dependencies !==
          (item.dependencies || []).map(dependencyText).join("\n")
        )
          changed.dependencies = values.dependencies;
        await api.put(`/action-items/${item.id}`, changed);
      } else await api.post("/action-items", values);
      toast(
        item
          ? "Action item updated. Original extraction remains traceable."
          : "Action item created as a user-provided record.",
      );
      onSaved();
      onClose();
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal
      title={item ? "Edit action item" : "Create action item"}
      description="Changes are human-provided states, not new transcript claims."
      onClose={() => !busy && onClose()}
      wide
    >
      {item?.source_snapshot?.text && (
        <details className="original-extraction">
          <summary>Original validated extraction</summary>
          <p>{item.source_snapshot.text}</p>
          <p className="field-hint">
            Owner: {item.source_snapshot.owner} · Deadline:{" "}
            {item.source_snapshot.due_date} · Priority:{" "}
            {item.source_snapshot.priority} · Status:{" "}
            {item.source_snapshot.status}
          </p>
          <SupportBadge item={item.source_snapshot} />
          <Evidence
            evidence={item.source_snapshot.evidence}
            meetingId={item.meeting_id}
          />
        </details>
      )}
      <form onSubmit={save} className="modal-form">
        {!item && !meetingId && (
          <Field label="Source meeting" required>
            <select
              required
              value={form.meeting_id}
              onChange={(event) => set("meeting_id", event.target.value)}
            >
              <option value="">Select a meeting</option>
              {meetings.data?.items.map((m) => (
                <option
                  value={m.id}
                  key={m.id}
                  disabled={["queued", "processing"].includes(
                    m.processing_status,
                  )}
                >
                  {m.title}
                </option>
              ))}
            </select>
            {meetings.error && (
              <span className="form-error">{meetings.error}</span>
            )}
          </Field>
        )}
        <Field label="Task" required>
          <textarea
            required
            rows={3}
            minLength={3}
            maxLength={3000}
            value={form.task}
            onChange={(event) => set("task", event.target.value)}
          />
        </Field>
        <div className="form-grid">
          <Field label="Owner">
            <input
              maxLength={120}
              value={form.owner}
              onChange={(event) => set("owner", event.target.value)}
              placeholder="Unassigned"
            />
          </Field>
          <Field
            label="Due date"
            hint={
              item?.due_date_text &&
              !item.due_date &&
              item.due_date_text !== "Not specified"
                ? `Original literal deadline: ${item.due_date_text}. Kept unless you select or clear a date.`
                : "Leave blank if no date is specified."
            }
          >
            <input
              type="date"
              value={form.due_date}
              onChange={(event) => {
                set("due_date", event.target.value);
                setClearLiteral(false);
              }}
            />
            {item?.due_date_text !== "Not specified" &&
              !item?.due_date &&
              item && (
                <button
                  className="text-btn"
                  type="button"
                  onClick={() => setClearLiteral(!clearLiteral)}
                >
                  {clearLiteral
                    ? "Keep original deadline"
                    : "Clear original literal deadline"}
                </button>
              )}
          </Field>
        </div>
        <div className="form-grid">
          <Field label="Priority">
            <select
              value={form.priority}
              onChange={(event) => set("priority", event.target.value)}
            >
              {PRIORITIES.map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </Field>
          <Field label="Status">
            <select
              value={form.status}
              onChange={(event) => set("status", event.target.value)}
            >
              {STATUSES.map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </Field>
        </div>
        <Field
          label="Dependencies"
          hint="One dependency per line. Manual additions are user-provided."
        >
          <textarea
            rows={2}
            maxLength={15000}
            value={form.dependencies}
            onChange={(event) => set("dependencies", event.target.value)}
          />
        </Field>
        <Field label="Notes">
          <textarea
            rows={3}
            maxLength={10000}
            value={form.notes}
            onChange={(event) => set("notes", event.target.value)}
          />
        </Field>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <div className="modal-actions">
          <Button
            variant="secondary"
            type="button"
            onClick={onClose}
            disabled={busy}
          >
            Cancel
          </Button>
          <Button type="submit" icon={Save} busy={busy}>
            Save action
          </Button>
        </div>
      </form>
    </Modal>
  );
}
