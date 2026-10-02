import { useState } from "react";
import { Link } from "react-router-dom";
import { Check, Pencil, Trash2 } from "lucide-react";
import { useToast } from "../context/ToastContext";
import { api, errorMessage } from "../services/api";
import { dateLabel, isOverdue, STATUSES } from "../services/format";
import { Avatar, Badge, ConfirmDialog, SupportBadge } from "./UI";
import { Evidence } from "./Evidence";
import ActionModal from "./ActionModal";

export default function ActionTable({
  items,
  reload,
  today,
  onLocate,
  compact = false,
  locked = false,
}) {
  const toast = useToast();
  const [editing, setEditing] = useState(null);
  const [deleting, setDeleting] = useState(null);
  const [busy, setBusy] = useState("");
  async function update(item, status) {
    setBusy(item.id);
    try {
      await api.put(`/action-items/${item.id}`, { status });
      reload();
      toast(
        status === "Completed"
          ? "Action marked complete."
          : `Status changed to ${status}.`,
      );
    } catch (error) {
      toast(errorMessage(error), "error");
    } finally {
      setBusy("");
    }
  }
  async function remove() {
    setBusy(deleting.id);
    try {
      await api.delete(`/action-items/${deleting.id}`);
      setDeleting(null);
      reload();
      toast("Action item deleted.");
    } catch (error) {
      toast(errorMessage(error), "error");
    } finally {
      setBusy("");
    }
  }
  return (
    <>
      <div className={`table-scroll ${compact ? "compact-table" : ""}`}>
        <table className="data-table action-table">
          <thead>
            <tr>
              <th className="complete-column">
                <span className="visually-hidden">Complete</span>
              </th>
              <th>Action item</th>
              <th>Owner</th>
              <th>Due date</th>
              <th>Priority</th>
              <th>Status</th>
              <th>
                <span className="visually-hidden">Manage</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {items.map((item, index) => (
              <tr
                key={item.id}
                className={item.status === "Completed" ? "completed-row" : ""}
              >
                <td className="complete-column">
                  <button
                    className={`task-check ${item.status === "Completed" ? "checked" : ""}`}
                    disabled={locked || busy === item.id}
                    aria-label={
                      item.status === "Completed"
                        ? `Reopen ${item.task}`
                        : `Complete ${item.task}`
                    }
                    onClick={() =>
                      update(
                        item,
                        item.status === "Completed" ? "Pending" : "Completed",
                      )
                    }
                  >
                    {item.status === "Completed" && <Check size={13} />}
                  </button>
                </td>
                <td data-label="Task" className="task-cell">
                  <p>{item.task.replace(/^Action:\s*/, "")}</p>
                  {!compact && (
                    <Link
                      className="task-meeting"
                      to={`/meetings/${item.meeting_id}`}
                    >
                      {item.meeting_title}
                    </Link>
                  )}
                  <div className="task-provenance">
                    <SupportBadge item={item} />
                    <Evidence
                      evidence={item.evidence}
                      onLocate={onLocate}
                      meetingId={item.meeting_id}
                    />
                  </div>
                  {item.notes && (
                    <small className="task-note">Note: {item.notes}</small>
                  )}
                </td>
                <td data-label="Owner">
                  <div
                    className={`owner-cell ${item.owner === "Unassigned" ? "unassigned" : ""}`}
                  >
                    <Avatar name={item.owner} index={index} small />
                    <span>{item.owner}</span>
                  </div>
                </td>
                <td
                  data-label="Due date"
                  className={isOverdue(item, today) ? "overdue-text" : ""}
                >
                  {item.due_date
                    ? dateLabel(item.due_date)
                    : item.due_date_text || "Not specified"}
                  {isOverdue(item, today) && <small>Overdue</small>}
                </td>
                <td data-label="Priority">
                  <Badge value={item.priority} />
                </td>
                <td data-label="Status">
                  <select
                    aria-label={`Status for ${item.task}`}
                    className={`status-select status-${item.status.toLowerCase().replaceAll(" ", "-")}`}
                    value={item.status}
                    disabled={locked || busy === item.id}
                    onChange={(event) => update(item, event.target.value)}
                  >
                    {STATUSES.map((s) => (
                      <option key={s}>{s}</option>
                    ))}
                  </select>
                </td>
                <td data-label="Manage">
                  <div className="row-actions">
                    <button
                      className="icon-btn"
                      aria-label={`Edit ${item.task}`}
                      onClick={() => setEditing(item)}
                      disabled={locked || busy === item.id}
                    >
                      <Pencil size={15} />
                    </button>
                    <button
                      className="icon-btn"
                      aria-label={`Delete ${item.task}`}
                      onClick={() => setDeleting(item)}
                      disabled={locked || busy === item.id}
                    >
                      <Trash2 size={15} />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {editing && (
        <ActionModal
          item={editing}
          onClose={() => setEditing(null)}
          onSaved={reload}
        />
      )}
      {deleting && (
        <ConfirmDialog
          title="Delete this action item?"
          message="This removes the manageable record. The original transcript and analysis report remain unchanged."
          onClose={() => !busy && setDeleting(null)}
          onConfirm={remove}
          busy={!!busy}
        />
      )}
    </>
  );
}
