import { useEffect, useState } from "react";
import {
  Link,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router-dom";
import {
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  FileText,
  Save,
  ShieldCheck,
  Sparkles,
  UploadCloud,
  Users,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { useResource } from "../hooks/useResource";
import { api, errorMessage } from "../services/api";
import { localDate } from "../services/format";
import {
  Button,
  ErrorState,
  Field,
  PageHeading,
  Skeleton,
} from "../components/UI";
import { UploadZone } from "../components/UploadZone";

export default function CreateMeeting() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const importId = params.get("document");
  const { user, configuration } = useAuth();
  const toast = useToast();
  const existing = useResource(id ? `/meetings/${id}` : null);
  const document = useResource(importId ? `/documents/${importId}` : null);
  const [form, setForm] = useState({
    title: "",
    date: localDate(user.timezone),
    participants: "",
    meeting_type: "Team sync",
    project: "",
    transcript: "",
  });
  const [files, setFiles] = useState([]);
  const [tab, setTab] = useState("paste");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [stage, setStage] = useState("");
  const [uploadProgress, setUploadProgress] = useState(null);
  const [savedId, setSavedId] = useState(id || null);
  const [importAttached, setImportAttached] = useState(false);
  useEffect(() => {
    if (existing.data) {
      const m = existing.data;
      setForm({
        title: m.title,
        date: m.date,
        participants: m.participants.join(", "),
        meeting_type: m.meeting_type,
        project: m.project,
        transcript: m.transcript,
      });
    }
  }, [existing.data]);
  function change(key, value) {
    setForm((old) => ({ ...old, [key]: value }));
  }
  async function submit(event) {
    event.preventDefault();
    const analyse = event.nativeEvent.submitter?.value === "analyse";
    setBusy(true);
    setError("");
    setUploadProgress(null);
    let meetingId = savedId;
    try {
      setStage("Saving meeting details");
      const values = {
        ...form,
        participants: form.participants
          .split(",")
          .map((name) => name.trim())
          .filter(Boolean),
      };
      const { data: meeting } = meetingId
        ? await api.put(`/meetings/${meetingId}`, values)
        : await api.post("/meetings", values);
      meetingId = meeting.id;
      setSavedId(meetingId);
      if (importId && !importAttached) {
        setStage("Attaching extracted document");
        await api.post(`/documents/${importId}/attach`, {
          meeting_id: meetingId,
        });
        setImportAttached(true);
      }
      for (const file of files) {
        const payload = new FormData();
        payload.append("file", file);
        payload.append("meeting_id", meetingId);
        payload.append("append_to_transcript", "true");
        setStage(`Uploading ${file.name}`);
        setUploadProgress(0);
        await api.post("/documents/upload", payload, {
          onUploadProgress: (progress) => {
            if (progress.total) {
              const percent = Math.round(
                (100 * progress.loaded) / progress.total,
              );
              setUploadProgress(percent);
              if (percent >= 100) setStage(`Extracting text from ${file.name}`);
            }
          },
        });
        setFiles((old) => old.filter((item) => item !== file));
      }
      if (analyse) {
        setStage("Queuing grounded analysis");
        await api.post(`/meetings/${meetingId}/process`);
      }
      toast(
        analyse
          ? "Meeting saved. Grounded analysis is queued."
          : "Meeting saved.",
      );
      navigate(`/meetings/${meetingId}`);
    } catch (failure) {
      setError(errorMessage(failure));
      toast(errorMessage(failure), "error");
      if (meetingId) {
        // Upload attachment may have modified the stored transcript. Refresh it
        // so retrying cannot overwrite a successfully imported document.
        try {
          const { data } = await api.get(`/meetings/${meetingId}`);
          change("transcript", data.transcript);
        } catch {
          /* error is already visible */
        }
      }
    } finally {
      setBusy(false);
      setStage("");
      setUploadProgress(null);
    }
  }
  if (id && existing.loading)
    return (
      <div className="page">
        <Skeleton height={80} />
        <Skeleton height={500} />
      </div>
    );
  if (existing.error || document.error)
    return (
      <div className="page">
        <ErrorState
          message={existing.error || document.error}
          onRetry={existing.error ? existing.reload : document.reload}
        />
      </div>
    );
  const processing = ["queued", "processing"].includes(
    existing.data?.processing_status,
  );
  return (
    <div className="page create-page">
      <Link to={id ? `/meetings/${id}` : "/meetings"} className="back-link">
        <ArrowLeft size={15} />
        {id ? "Back to meeting" : "All meetings"}
      </Link>
      <PageHeading
        eyebrow="MAKE THE CONVERSATION COUNT"
        title={id ? "Edit meeting" : "Create a meeting"}
        description="A little context. A transcript. A lot more clarity."
      />
      <div className="create-grid">
        <form className="create-form" onSubmit={submit}>
          <section className="card form-card">
            <div className="form-section-heading">
              <span>01</span>
              <div>
                <h2>Meeting context</h2>
                <p>
                  Help organise the conversation, without filling in the blanks.
                </p>
              </div>
            </div>
            <Field label="Meeting title" required>
              <input
                required
                minLength={2}
                maxLength={200}
                value={form.title}
                onChange={(event) => change("title", event.target.value)}
                placeholder="e.g. Platform sprint planning"
                disabled={busy || processing}
              />
            </Field>
            <div className="form-grid">
              <Field label="Meeting date" required>
                <input
                  required
                  type="date"
                  value={form.date}
                  onChange={(event) => change("date", event.target.value)}
                  disabled={busy || processing}
                />
              </Field>
              <Field label="Meeting type">
                <input
                  list="meeting-types"
                  value={form.meeting_type}
                  maxLength={80}
                  minLength={2}
                  required
                  onChange={(event) =>
                    change("meeting_type", event.target.value)
                  }
                  disabled={busy || processing}
                />
                <datalist id="meeting-types">
                  {[
                    "Team sync",
                    "Sprint planning",
                    "Design review",
                    "Technical review",
                    "Project review",
                    "Retrospective",
                    "Customer call",
                    "One-on-one",
                  ].map((type) => (
                    <option value={type} key={type} />
                  ))}
                </datalist>
              </Field>
            </div>
            <Field
              label="Participants"
              hint="Separate names with commas. These are provided metadata, not inferred speakers."
            >
              <div className="input-icon">
                <Users size={17} />
                <input
                  value={form.participants}
                  maxLength={12000}
                  onChange={(event) =>
                    change("participants", event.target.value)
                  }
                  placeholder="Maya, Rahul, Alex"
                  disabled={busy || processing}
                />
              </div>
            </Field>
            <Field label="Project / team">
              <input
                value={form.project}
                maxLength={150}
                onChange={(event) => change("project", event.target.value)}
                placeholder="e.g. Platform team / Atlas"
                disabled={busy || processing}
              />
            </Field>
          </section>
          <section className="card form-card">
            <div className="form-section-heading">
              <span>02</span>
              <div>
                <h2>The original conversation</h2>
                <p>Messy notes are welcome. Unsupported facts aren’t.</p>
              </div>
            </div>
            <div className="tabs">
              <button
                type="button"
                className={tab === "paste" ? "active" : ""}
                onClick={() => setTab("paste")}
              >
                <FileText size={15} />
                Paste transcript
              </button>
              <button
                type="button"
                className={tab === "upload" ? "active" : ""}
                onClick={() => setTab("upload")}
              >
                <UploadCloud size={15} />
                Upload documents
                {files.length > 0 && (
                  <span className="count-badge">{files.length}</span>
                )}
              </button>
            </div>
            {importId && document.data && (
              <div className="info-callout">
                <FileText size={18} />
                <div>
                  <strong>{document.data.filename}</strong>
                  <p>
                    {document.data.attached_to_transcript
                      ? "This document is already attached to a meeting. Select an unattached document to import."
                      : "Extracted text and page references will be attached when you save."}
                  </p>
                </div>
              </div>
            )}
            {tab === "paste" ? (
              <>
                <textarea
                  className="transcript-input"
                  aria-label="Meeting transcript"
                  rows={16}
                  value={form.transcript}
                  maxLength={configuration?.max_transcript_chars || 150000}
                  disabled={busy || processing}
                  onChange={(event) => change("transcript", event.target.value)}
                  placeholder={
                    "Maya: Let’s discuss the deployment plan.\nRahul: I’ll add rollback tests by 2026-10-08.\nMaya: We agreed to use a canary release.\n\nPaste the actual conversation here. Speaker labels help measure speaking contribution."
                  }
                />
                <div className="transcript-input-footer">
                  <span>
                    <LockIcon />
                    Used only in your workspace
                  </span>
                  <span>
                    {form.transcript.length.toLocaleString()} /{" "}
                    {(
                      configuration?.max_transcript_chars || 150000
                    ).toLocaleString()}{" "}
                    characters
                  </span>
                </div>
              </>
            ) : (
              <UploadZone
                files={files}
                onChange={setFiles}
                maxBytes={configuration?.max_upload_size}
                disabled={busy || processing}
              />
            )}
            {id && existing.data?.summary && (
              <div className="warning-callout">
                Changing transcript content clears stale summaries and vectors.
                Human-edited tasks are kept as user-provided records. Reanalyse
                to generate fresh evidence.
              </div>
            )}
          </section>
          {processing && (
            <div className="warning-callout">
              This meeting is processing. Editing is locked until the job
              finishes.
            </div>
          )}
          {error && (
            <div className="form-error" role="alert">
              {error}
              {savedId && (
                <Link to={`/meetings/${savedId}`}> Open the saved meeting</Link>
              )}
            </div>
          )}
          {busy && (
            <div className="processing-inline" role="status">
              <Sparkles size={18} />
              <span>{stage}</span>
              {uploadProgress !== null && (
                <div className="upload-progress">
                  <i style={{ width: `${uploadProgress}%` }} />
                </div>
              )}
            </div>
          )}
          <div className="form-actions">
            <Link
              to={id ? `/meetings/${id}` : "/meetings"}
              className="btn btn-ghost"
            >
              Cancel
            </Link>
            <Button
              variant="secondary"
              icon={Save}
              type="submit"
              value="draft"
              disabled={busy || processing}
            >
              Save {id ? "changes" : "draft"}
            </Button>
            <Button
              icon={Sparkles}
              type="submit"
              value="analyse"
              busy={busy}
              disabled={
                processing ||
                ((!form.transcript.trim() ||
                  form.transcript.trim().length < 10) &&
                  !files.length &&
                  !importId) ||
                (document.data?.attached_to_transcript && !id)
              }
            >
              Save & analyse <ArrowRight size={15} />
            </Button>
          </div>
        </form>
        <aside className="create-aside">
          <div className="card grounding-guide">
            <div className="guide-icon">
              <ShieldCheck size={27} />
            </div>
            <h3>Clarity with receipts.</h3>
            <p>Grounded separates what’s explicit from what’s missing.</p>
            <ul>
              <li>
                <CheckCircle2 size={17} />
                <span>Every claim includes a source quote.</span>
              </li>
              <li>
                <CheckCircle2 size={17} />
                <span>
                  Missing owners stay <b>Unassigned</b>.
                </span>
              </li>
              <li>
                <CheckCircle2 size={17} />
                <span>
                  Missing deadlines stay <b>Not specified</b>.
                </span>
              </li>
              <li>
                <CheckCircle2 size={17} />
                <span>Ambiguity is flagged, never hidden.</span>
              </li>
            </ul>
          </div>
          <div className="card pipeline-guide">
            <h3>From transcript to next steps</h3>
            <p>The processing pipeline</p>
            <ol>
              {[
                "Clean & preserve source lines",
                "Chunk & index the transcript",
                "Extract structured intelligence",
                "Verify every source claim",
                "Save manageable action records",
              ].map((step, index) => (
                <li key={step}>
                  <span>{index + 1}</span>
                  {step}
                </li>
              ))}
            </ol>
          </div>
          <div className="mode-note">
            <Sparkles size={17} />
            <div>
              <strong>
                {configuration?.provider === "openai"
                  ? "OpenAI structured processing"
                  : "Local extractive mode"}
              </strong>
              <p>
                {configuration?.provider === "openai"
                  ? "Extraction and independent verification use your configured OpenAI model."
                  : "Conservative, real source extraction. Configure OPENAI_API_KEY in .env for LLM synthesis and neural semantic search."}
              </p>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
function LockIcon() {
  return <ShieldCheck size={12} />;
}
