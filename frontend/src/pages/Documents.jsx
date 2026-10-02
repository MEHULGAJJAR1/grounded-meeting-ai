import { useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowUpRight,
  ChevronLeft,
  ChevronRight,
  Download,
  Eye,
  FileText,
  Link2,
  Plus,
  Trash2,
  UploadCloud,
} from "lucide-react";
import { useResource } from "../hooks/useResource";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { api, downloadFile, errorMessage } from "../services/api";
import { dateLabel, fileSize } from "../services/format";
import {
  Badge,
  Button,
  ConfirmDialog,
  EmptyState,
  ErrorState,
  Field,
  Modal,
  PageHeading,
  Skeleton,
} from "../components/UI";
import { UploadZone } from "../components/UploadZone";

export default function Documents() {
  const [offset, setOffset] = useState(0);
  const resource = useResource(`/documents?limit=25&offset=${offset}`);
  const meetings = useResource("/meetings?limit=100");
  const { configuration } = useAuth();
  const toast = useToast();
  const [files, setFiles] = useState([]);
  const [meetingId, setMeetingId] = useState("");
  const [busy, setBusy] = useState("");
  const [stage, setStage] = useState("");
  const [percent, setPercent] = useState(null);
  const [preview, setPreview] = useState(null);
  const [page, setPage] = useState(0);
  const [attaching, setAttaching] = useState(null);
  const [target, setTarget] = useState("");
  const [deleting, setDeleting] = useState(null);
  const items = resource.data?.items || [];
  const total = resource.data?.total || 0;
  async function upload() {
    setBusy("upload");
    setPercent(0);
    try {
      for (const file of files) {
        const payload = new FormData();
        payload.append("file", file);
        if (meetingId) payload.append("meeting_id", meetingId);
        setStage(`Uploading ${file.name}`);
        await api.post("/documents/upload", payload, {
          onUploadProgress: (progress) => {
            if (progress.total) {
              const p = Math.round((progress.loaded / progress.total) * 100);
              setPercent(p);
              if (p === 100) setStage(`Extracting text from ${file.name}`);
            }
          },
        });
        setFiles((old) => old.filter((value) => value !== file));
      }
      resource.reload();
      meetings.reload();
      toast(
        meetingId
          ? "Documents extracted and appended. Reanalyse the meeting for fresh results."
          : "Documents extracted. Attach them to a meeting for AI analysis and search.",
      );
    } catch (error) {
      toast(errorMessage(error), "error");
      resource.reload();
    } finally {
      setBusy("");
      setStage("");
      setPercent(null);
    }
  }
  async function showDocument(item) {
    setBusy(item.id);
    try {
      const { data } = await api.get(`/documents/${item.id}`);
      setPreview(data);
      setPage(0);
    } catch (error) {
      toast(errorMessage(error), "error");
    } finally {
      setBusy("");
    }
  }
  async function download(item) {
    try {
      await downloadFile(`/documents/${item.id}/download`, item.filename);
    } catch (error) {
      toast(errorMessage(error), "error");
    }
  }
  async function attach(event) {
    event.preventDefault();
    setBusy("attach");
    try {
      await api.post(`/documents/${attaching.id}/attach`, {
        meeting_id: target,
      });
      setAttaching(null);
      resource.reload();
      meetings.reload();
      toast(
        "Document attached. Process the meeting to generate current intelligence.",
      );
    } catch (error) {
      toast(errorMessage(error), "error");
    } finally {
      setBusy("");
    }
  }
  async function remove() {
    setBusy("delete");
    try {
      await api.delete(`/documents/${deleting.id}`);
      setDeleting(null);
      resource.reload();
      toast(
        "Stored document deleted. Previously imported transcript text is unchanged.",
      );
    } catch (error) {
      toast(errorMessage(error), "error");
    } finally {
      setBusy("");
    }
  }
  const meetingNames = Object.fromEntries(
    (meetings.data?.items || []).map((m) => [m.id, m.title]),
  );
  return (
    <div className="page">
      <PageHeading
        eyebrow="THE SOURCE OF YOUR INTELLIGENCE"
        title="Document library"
        description="Original files, extracted text and a traceable processing history."
      >
        <Link className="btn btn-secondary" to="/meetings/new">
          <Plus size={16} />
          Create a meeting
        </Link>
      </PageHeading>
      <div className="card document-upload-card">
        <div>
          <h2>Bring the conversation in</h2>
          <p>
            Text is extracted from actual file content. Scanned PDFs need OCR
            outside this app.
          </p>
          <UploadZone
            files={files}
            onChange={setFiles}
            maxBytes={configuration?.max_upload_size}
            disabled={busy === "upload"}
          />
        </div>
        <div className="document-upload-options">
          <div className="eyebrow">OPTIONAL MEETING LINK</div>
          <Field
            label="Append to a meeting"
            hint="Adding text clears stale AI results, while keeping human-edited actions."
          >
            <select
              value={meetingId}
              onChange={(event) => setMeetingId(event.target.value)}
              disabled={busy === "upload"}
            >
              <option value="">Extract only — attach later</option>
              {meetings.data?.items.map((m) => (
                <option
                  value={m.id}
                  key={m.id}
                  disabled={["processing", "queued"].includes(
                    m.processing_status,
                  )}
                >
                  {m.title}
                </option>
              ))}
            </select>
          </Field>
          <div className="document-upload-info">
            <FileText size={19} />
            <p>
              PDF page references and DOCX structure are preserved. CSV rows
              become readable transcript lines.
            </p>
          </div>
          <Button
            icon={UploadCloud}
            busy={busy === "upload"}
            onClick={upload}
            disabled={!files.length}
          >
            {files.length > 1
              ? `Upload ${files.length} documents`
              : "Upload document"}
          </Button>
          {stage && (
            <div className="upload-status" role="status">
              <span>{stage}</span>
              {percent !== null && (
                <div className="upload-progress">
                  <i style={{ width: `${percent}%` }} />
                </div>
              )}
            </div>
          )}
        </div>
      </div>
      <div className="results-heading">
        <span>
          {total} stored {total === 1 ? "document" : "documents"}
        </span>
        <span>Newest uploads first</span>
      </div>
      {resource.error ? (
        <ErrorState message={resource.error} onRetry={resource.reload} />
      ) : resource.loading ? (
        <Skeleton height={300} />
      ) : !items.length ? (
        <div className="card">
          <EmptyState
            compact
            icon={FileText}
            title="A clean slate for your source files."
            description="Upload a transcript above. Every file keeps its extraction status and any processing errors."
          />
        </div>
      ) : (
        <div className="card table-scroll">
          <table className="data-table document-table">
            <thead>
              <tr>
                <th>Document</th>
                <th>Meeting</th>
                <th>Uploaded</th>
                <th>Extraction</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id}>
                  <td data-label="Document">
                    <div className="document-name">
                      <span className={`file-icon file-${item.file_type}`}>
                        <FileText size={21} />
                        <small>{item.file_type.toUpperCase()}</small>
                      </span>
                      <span>
                        <button
                          className="table-title text-btn"
                          onClick={() => showDocument(item)}
                        >
                          {item.filename}
                        </button>
                        <small>
                          {fileSize(item.size_bytes)} · {item.page_count}{" "}
                          extracted{" "}
                          {item.page_count === 1 ? "section" : "pages"}
                        </small>
                      </span>
                    </div>
                  </td>
                  <td data-label="Meeting">
                    {item.meeting_id ? (
                      <Link
                        className="doc-meeting-link"
                        to={`/meetings/${item.meeting_id}`}
                      >
                        {meetingNames[item.meeting_id] || "Open linked meeting"}
                        <ArrowUpRight size={13} />
                      </Link>
                    ) : (
                      <span className="muted">Not attached</span>
                    )}
                  </td>
                  <td data-label="Uploaded">
                    {dateLabel(item.created_at, { year: "numeric" })}
                  </td>
                  <td data-label="Extraction">
                    <Badge value={item.processing_status}>
                      {item.processing_status === "completed"
                        ? "Extracted"
                        : item.processing_status}
                    </Badge>
                    {item.processing_error && (
                      <small className="form-error">
                        {item.processing_error}
                      </small>
                    )}
                  </td>
                  <td data-label="Actions">
                    <div className="row-actions">
                      <button
                        className="icon-btn"
                        aria-label={`Preview ${item.filename}`}
                        onClick={() => showDocument(item)}
                        disabled={busy === item.id}
                      >
                        <Eye size={17} />
                      </button>
                      <button
                        className="icon-btn"
                        aria-label={`Download ${item.filename}`}
                        onClick={() => download(item)}
                      >
                        <Download size={17} />
                      </button>
                      {!item.attached_to_transcript &&
                        item.processing_status === "completed" && (
                          <button
                            className="icon-btn"
                            aria-label={`Attach ${item.filename}`}
                            onClick={() => {
                              setAttaching(item);
                              setTarget("");
                            }}
                          >
                            <Link2 size={17} />
                          </button>
                        )}
                      <button
                        className="icon-btn"
                        aria-label={`Delete ${item.filename}`}
                        onClick={() => setDeleting(item)}
                      >
                        <Trash2 size={17} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {total > 25 && (
        <div className="pagination">
          <span>
            {offset + 1}–{Math.min(total, offset + 25)} of {total}
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
            Next <ChevronRight size={14} />
          </Button>
        </div>
      )}
      {preview && (
        <Modal
          title={preview.filename}
          description={`${preview.file_type.toUpperCase()} · ${fileSize(preview.size_bytes)} · ${preview.processing_status}`}
          onClose={() => setPreview(null)}
          wide
        >
          {preview.processing_error ? (
            <div className="form-error">{preview.processing_error}</div>
          ) : (
            <>
              <div className="document-preview-toolbar">
                <span>
                  {preview.file_type === "pdf"
                    ? `PDF page ${preview.pages[page]?.page}`
                    : `Extracted section ${page + 1}`}{" "}
                  of {preview.pages.length}
                </span>
                <Button
                  variant="ghost"
                  disabled={page === 0}
                  icon={ChevronLeft}
                  onClick={() => setPage(page - 1)}
                >
                  Previous
                </Button>
                <Button
                  variant="ghost"
                  disabled={page + 1 >= preview.pages.length}
                  onClick={() => setPage(page + 1)}
                >
                  Next <ChevronRight size={14} />
                </Button>
              </div>
              <pre className="document-preview">
                {preview.pages[page]
                  ? preview.pages[page].text ||
                    "No selectable text on this page. Scanned content needs OCR outside this app."
                  : preview.extracted_text}
              </pre>
            </>
          )}
          <div className="modal-actions">
            {!preview.attached_to_transcript &&
              preview.processing_status === "completed" && (
                <Link
                  className="btn btn-secondary"
                  to={`/meetings/new?document=${preview.id}`}
                >
                  <Plus size={15} />
                  Create meeting from file
                </Link>
              )}
            <Button icon={Download} onClick={() => download(preview)}>
              Download original
            </Button>
          </div>
        </Modal>
      )}
      {attaching && (
        <Modal
          title="Attach document to a meeting"
          description={attaching.filename}
          onClose={() => !busy && setAttaching(null)}
        >
          <form className="modal-form" onSubmit={attach}>
            <Field label="Select meeting" required>
              <select
                value={target}
                onChange={(event) => setTarget(event.target.value)}
                required
              >
                <option value="">Choose a meeting</option>
                {meetings.data?.items.map((m) => (
                  <option
                    key={m.id}
                    value={m.id}
                    disabled={["processing", "queued"].includes(
                      m.processing_status,
                    )}
                  >
                    {m.title}
                  </option>
                ))}
              </select>
            </Field>
            <p className="field-hint">
              This appends the extracted text and page references. Existing AI
              results are invalidated; reanalyse to refresh them.
            </p>
            <div className="modal-actions">
              <Button
                variant="secondary"
                type="button"
                onClick={() => setAttaching(null)}
                disabled={!!busy}
              >
                Cancel
              </Button>
              <Button type="submit" busy={busy === "attach"} icon={Link2}>
                Attach document
              </Button>
            </div>
          </form>
        </Modal>
      )}
      {deleting && (
        <ConfirmDialog
          title="Delete the stored document?"
          message="The original upload and its extraction record will be removed. Text already imported into a meeting transcript remains there; edit or delete the meeting to remove that copy."
          busy={busy === "delete"}
          onClose={() => !busy && setDeleting(null)}
          onConfirm={remove}
        />
      )}
    </div>
  );
}
