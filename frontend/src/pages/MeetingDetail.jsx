import { TranscriptBody } from "../components/meeting/TranscriptPanel";
import { ParticipantsBody } from "../components/meeting/ParticipantPanel";
import { RisksBody, QuestionsBody } from "../components/meeting/IssuePanels";
import {
  SummaryBody,
  DecisionsBody,
} from "../components/meeting/SummaryPanels";
import { useEffect, useState } from "react";
import {
  Link,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router-dom";
import {
  ArrowLeft,
  CalendarDays,
  CheckCircle2,
  ChevronDown,
  CircleHelp,
  Download,
  FileText,
  Flag,
  Folder,
  ListTodo,
  MessageSquareText,
  Pencil,
  Plus,
  Quote,
  ShieldCheck,
  Sparkles,
  Tags,
  Trash2,
  TriangleAlert,
  Users,
  Waypoints,
} from "lucide-react";
import { useResource } from "../hooks/useResource";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { api, copyText, downloadFile, errorMessage } from "../services/api";
import { dateLabel, localDate } from "../services/format";
import {
  AvatarGroup,
  Badge,
  Button,
  ConfirmDialog,
  EmptyState,
  ErrorState,
  Field,
  Modal,
  Section,
  Skeleton,
} from "../components/UI";
import { ClaimList, Evidence } from "../components/Evidence";
import ActionModal from "../components/ActionModal";
import ActionTable from "../components/ActionTable";
import GroundingPanel from "../components/GroundingPanel";
import ProcessingPanel from "../components/ProcessingPanel";

export default function MeetingDetail() {
  const { id } = useParams();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const resource = useResource(`/meetings/${id}`);
  const { user } = useAuth();
  const toast = useToast();
  const [opens, setOpens] = useState({ transcript: !!params.get("line") });
  const [highlight, setHighlight] = useState(null);
  const [summaryTab, setSummaryTab] = useState("executive_summary");
  const [decisionTab, setDecisionTab] = useState("All");
  const [creatingAction, setCreatingAction] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [busy, setBusy] = useState("");
  const [exportOpen, setExportOpen] = useState(false);
  const [question, setQuestion] = useState(null);
  const [answer, setAnswer] = useState("");
  const [pollError, setPollError] = useState("");
  const meeting = resource.data;
  const locked = ["queued", "processing"].includes(meeting?.processing_status);
  useEffect(() => {
    if (!locked) return;
    let active = true;
    let requestActive = false;
    const interval = setInterval(async () => {
      if (requestActive) return;
      requestActive = true;
      try {
        const { data } = await api.get(`/meetings/${id}/processing-status`);
        if (!active) return;
        resource.setData((old) => ({
          ...old,
          processing_status: data.status,
          processing_stage: data.stage,
          processing_progress: data.progress,
          processing_error: data.error,
        }));
        if (!["queued", "processing"].includes(data.status)) {
          clearInterval(interval);
          resource.reload();
          if (data.status === "completed") toast("Grounded analysis is ready.");
        }
      } catch (failure) {
        if (active) {
          setPollError(errorMessage(failure));
          clearInterval(interval);
        }
      } finally {
        requestActive = false;
      }
    }, 1200);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, [locked, id, resource.reload]);
  useEffect(() => {
    if (meeting && params.get("line"))
      locate({
        line_start: Number(params.get("line")),
        line_end: Number(params.get("line")),
      });
  }, [meeting?.id]);
  function section(title, Icon, content, count, sectionId, action) {
    const key = sectionId || title.toLowerCase().replaceAll(" ", "-");
    return (
      <Section
        id={key}
        title={title}
        icon={Icon}
        count={count}
        open={opens[key] ?? true}
        onToggle={(isOpen) =>
          setOpens((old) =>
            old[key] === isOpen ? old : { ...old, [key]: isOpen },
          )
        }
        action={action}
      >
        {content}
      </Section>
    );
  }
  function locate(evidence) {
    setOpens((old) => ({ ...old, transcript: true }));
    setHighlight([evidence.line_start, evidence.line_end]);
    setTimeout(
      () =>
        document
          .getElementById(`transcript-line-${evidence.line_start}`)
          ?.scrollIntoView({ behavior: "smooth", block: "center" }),
      80,
    );
  }
  async function process() {
    setBusy("process");
    try {
      await api.post(`/meetings/${id}/process`);
      setPollError("");
      resource.reload();
      toast("Analysis queued. Progress reflects real processing stages.");
    } catch (error) {
      toast(errorMessage(error), "error");
    } finally {
      setBusy("");
    }
  }
  async function remove() {
    setBusy("delete");
    try {
      await api.delete(`/meetings/${id}`);
      toast("Meeting deleted.");
      navigate("/meetings");
    } catch (error) {
      toast(errorMessage(error), "error");
    } finally {
      setBusy("");
    }
  }
  async function exportFile(format) {
    setBusy(`export-${format}`);
    try {
      await downloadFile(
        `/meetings/${id}/export/${format}`,
        `meeting.${format}`,
      );
      setExportOpen(false);
      toast("Meeting exported with evidence and provenance.");
    } catch (error) {
      toast(errorMessage(error), "error");
    } finally {
      setBusy("");
    }
  }
  async function copy(text) {
    try {
      await copyText(text);
      toast("Copied to clipboard.");
    } catch (error) {
      toast(error.message, "error");
    }
  }
  async function riskStatus(risk) {
    setBusy(risk.id);
    try {
      await api.put(`/risks/${risk.id}`, {
        status: risk.status === "Open" ? "Resolved" : "Open",
      });
      resource.reload();
      toast("Risk state updated as a user-provided change.");
    } catch (error) {
      toast(errorMessage(error), "error");
    } finally {
      setBusy("");
    }
  }
  async function saveAnswer(event) {
    event.preventDefault();
    setBusy(question.id);
    try {
      await api.put(`/questions/${question.id}`, {
        status: "Answered",
        answer,
      });
      setQuestion(null);
      resource.reload();
      toast("Human-provided answer saved.");
    } catch (error) {
      toast(errorMessage(error), "error");
    } finally {
      setBusy("");
    }
  }
  async function reopenQuestion(item) {
    try {
      await api.put(`/questions/${item.id}`, {
        status: "Unanswered",
        answer: "",
      });
      resource.reload();
    } catch (error) {
      toast(errorMessage(error), "error");
    }
  }
  if (resource.loading && !meeting)
    return (
      <div className="page">
        <Skeleton height={120} />
        <Skeleton height={330} />
        <Skeleton height={280} />
      </div>
    );
  if (resource.error)
    return (
      <div className="page">
        <ErrorState message={resource.error} onRetry={resource.reload} />
      </div>
    );
  if (!meeting) return null;
  const summary = meeting.summary;
  const report = meeting.grounding_report;
  const decisions = meeting.decisions.filter(
    (d) => decisionTab === "All" || d.decision_type === decisionTab,
  );
  const speakerData = meeting.participant_analysis
    .filter((p) => p.word_count !== null)
    .map((p) => ({ name: p.name, words: p.word_count }));
  const transcriptLines = (
    meeting.cleaned_transcript || meeting.transcript
  ).split("\n");
  return (
    <div className="page meeting-detail-page">
      <Link to="/meetings" className="back-link">
        <ArrowLeft size={15} />
        All meetings
      </Link>
      <div className="meeting-detail-heading">
        <div>
          <div className="meeting-heading-badges">
            <Badge value={meeting.processing_status}>
              {meeting.processing_status === "completed"
                ? "Analysed"
                : meeting.processing_status}
            </Badge>
            {meeting.is_demo && (
              <span className="sample-label">Sample meeting</span>
            )}
            {meeting.analysis_provider && (
              <span className="provider-label">
                <Sparkles size={12} />
                {meeting.analysis_provider}
              </span>
            )}
          </div>
          <h1>{meeting.title}</h1>
          <div className="meeting-metadata">
            <span>
              <CalendarDays size={15} />
              {dateLabel(meeting.date, { year: "numeric" })}
            </span>
            <span>
              <MessageSquareText size={15} />
              {meeting.meeting_type}
            </span>
            {meeting.project && (
              <span>
                <Folder size={15} />
                {meeting.project}
              </span>
            )}
            <span>
              <Users size={15} />
              {meeting.participants.length} participants
            </span>
          </div>
          <div className="participant-inline">
            <AvatarGroup names={meeting.participants} />
            <span>
              {meeting.participants.join(", ") || "No participants provided"}
            </span>
          </div>
        </div>
        <div className="detail-header-actions">
          <Link
            to={`/meetings/${id}/edit`}
            className={`btn btn-secondary ${locked ? "disabled-link" : ""}`}
            aria-disabled={locked}
          >
            <Pencil size={15} />
            Edit
          </Link>
          <div className="export-wrap">
            <Button
              variant="secondary"
              icon={Download}
              onClick={() => setExportOpen(!exportOpen)}
              disabled={locked}
              busy={busy.startsWith("export-")}
            >
              Export <ChevronDown size={14} />
            </Button>
            {exportOpen && (
              <div className="export-menu">
                {[
                  ["pdf", "PDF document"],
                  ["docx", "Word document"],
                  ["json", "Structured JSON"],
                  ["markdown", "Markdown notes"],
                  ["csv", "Actions CSV"],
                ].map(([value, title]) => (
                  <button
                    onClick={() => exportFile(value)}
                    key={value}
                    disabled={!!busy}
                  >
                    <FileText size={15} />
                    {title}
                  </button>
                ))}
              </div>
            )}
          </div>
          <button
            aria-label="Delete meeting"
            className="icon-btn"
            onClick={() => setDeleteOpen(true)}
            disabled={locked}
          >
            <Trash2 size={18} />
          </button>
          <Button
            icon={Sparkles}
            busy={busy === "process"}
            disabled={locked || meeting.transcript.trim().length < 10}
            onClick={process}
          >
            {summary ? "Reanalyse" : "Analyse meeting"}
          </Button>
        </div>
      </div>
      {locked && <ProcessingPanel meeting={meeting} />}
      {pollError && (
        <ErrorState
          message={pollError}
          onRetry={() => {
            setPollError("");
            resource.reload();
          }}
        />
      )}
      {meeting.processing_status === "failed" && (
        <ErrorState
          message={
            meeting.processing_error +
            (summary ? " Previous successful analysis is shown below." : "")
          }
          onRetry={process}
        />
      )}
      {summary && !locked && (
        <div className="meeting-health-row">
          {[
            [meeting.health.decisions, "Decisions", CheckCircle2],
            [meeting.health.action_items, "Actions", ListTodo],
            [meeting.health.risks, "Open risks", TriangleAlert],
            [meeting.health.unresolved_questions, "Open questions", CircleHelp],
          ].map(([count, label, Icon]) => (
            <div key={label}>
              <Icon size={18} />
              <strong>{count}</strong>
              <span>{label}</span>
            </div>
          ))}
          <a href="#grounding-check" className="health-grounding">
            <ShieldCheck size={18} />
            <strong>{report?.evidence_pass_rate}%</strong>
            <span>evidence pass rate</span>
          </a>
        </div>
      )}
      {!summary && !locked ? (
        <div className="card">
          <EmptyState
            icon={Sparkles}
            title="The conversation is here. Let’s find the clarity."
            description={
              meeting.transcript.trim()
                ? "Process this transcript to extract decisions, action items, risks and the exact source evidence behind them."
                : "Add a transcript or attach an uploaded document before starting analysis."
            }
          >
            {meeting.transcript.trim().length >= 10 ? (
              <Button
                icon={Sparkles}
                busy={busy === "process"}
                onClick={process}
              >
                Analyse meeting
              </Button>
            ) : (
              <Link className="btn btn-primary" to={`/meetings/${id}/edit`}>
                <Plus size={16} />
                Add a transcript
              </Link>
            )}
          </EmptyState>
        </div>
      ) : null}
      {summary && (
        <div className="meeting-sections">
          {section(
            "Summary",
            FileText,
            <SummaryBody
              summaryTab={summaryTab}
              setSummaryTab={setSummaryTab}
              copy={copy}
              summary={summary}
              meeting={meeting}
              locate={locate}
            />,
            undefined,
            "summary",
          )}
          {section(
            "Key discussion points",
            Quote,
            <ClaimList items={summary.key_points} onLocate={locate} />,
            summary.key_points.length,
            "key-points",
          )}
          {section(
            "Decisions",
            CheckCircle2,
            <DecisionsBody
              decisionTab={decisionTab}
              setDecisionTab={setDecisionTab}
              decisions={decisions}
              locate={locate}
            />,
            meeting.decisions.length,
            "decisions",
          )}
          {section(
            "Action items",
            ListTodo,
            meeting.action_items.length ? (
              <ActionTable
                items={meeting.action_items}
                compact
                locked={locked}
                today={localDate(user.timezone)}
                reload={resource.reload}
                onLocate={locate}
              />
            ) : (
              <p className="muted empty-line">
                No supported actions extracted. You can create a user-provided
                task.
              </p>
            ),
            meeting.action_items.length,
            "action-items",
            <Button
              variant="secondary"
              icon={Plus}
              onClick={() => setCreatingAction(true)}
              disabled={locked}
            >
              Add action
            </Button>,
          )}
          {section(
            "Risks & blockers",
            TriangleAlert,
            <RisksBody
              meeting={meeting}
              locked={locked}
              busy={busy}
              riskStatus={riskStatus}
              locate={locate}
            />,
            meeting.risks.length,
            "risks",
          )}
          {section(
            "Unanswered questions",
            CircleHelp,
            <QuestionsBody
              meeting={meeting}
              locked={locked}
              reopenQuestion={reopenQuestion}
              setQuestion={setQuestion}
              setAnswer={setAnswer}
              locate={locate}
            />,
            meeting.questions.length,
            "questions",
          )}
          {section(
            "Topics discussed",
            Tags,
            meeting.topics.length ? (
              <div className="topics-grid">
                {meeting.topics.map((t) => (
                  <div className="topic-card" key={t.id}>
                    <Tags size={16} />
                    <strong>{t.name}</strong>
                    <Evidence evidence={t.evidence} onLocate={locate} />
                  </div>
                ))}
              </div>
            ) : (
              <p className="muted empty-line">No supported topics extracted.</p>
            ),
            meeting.topics.length,
            "topics",
          )}
          {section(
            "Participants",
            Users,
            <ParticipantsBody speakerData={speakerData} meeting={meeting} />,
            meeting.participant_analysis.length,
            "participants",
          )}
          {section(
            "Follow-ups & commitments",
            Flag,
            <div className="subsection-grid">
              <div>
                <h3>Follow-up items</h3>
                <ClaimList items={summary.follow_ups} onLocate={locate} />
              </div>
              <div>
                <h3>Important commitments</h3>
                <ClaimList items={summary.commitments} onLocate={locate} />
              </div>
            </div>,
            undefined,
            "follow-ups",
          )}
          {section(
            "Dependencies & source mentions",
            Waypoints,
            <>
              <h3 className="subsection-heading">Dependencies</h3>
              <ClaimList items={summary.dependencies} onLocate={locate} />
              <div className="subsection-grid">
                <div>
                  <h3>Mentioned projects</h3>
                  <ClaimList items={summary.projects} onLocate={locate} />
                </div>
                <div>
                  <h3>Mentioned people</h3>
                  <ClaimList items={summary.people} onLocate={locate} />
                </div>
              </div>
              <h3 className="subsection-heading">
                Important dates (literal source wording)
              </h3>
              <ClaimList items={summary.important_dates} onLocate={locate} />
            </>,
            undefined,
            "dependencies",
          )}
          {section(
            "Grounding check",
            ShieldCheck,
            <GroundingPanel report={report} onLocate={locate} />,
            report.checked_claims,
            "grounding-check",
          )}
        </div>
      )}
      {section(
        "Original transcript",
        FileText,
        <TranscriptBody
          copy={copy}
          meeting={meeting}
          transcriptLines={transcriptLines}
          highlight={highlight}
        />,
        undefined,
        "transcript",
      )}
      {creatingAction && (
        <ActionModal
          meetingId={id}
          onClose={() => setCreatingAction(false)}
          onSaved={resource.reload}
        />
      )}
      {deleteOpen && (
        <ConfirmDialog
          title="Delete this meeting?"
          message="All associated transcripts, summaries, action items, vectors and uploaded files will be permanently removed."
          busy={busy === "delete"}
          onClose={() => !busy && setDeleteOpen(false)}
          onConfirm={remove}
        />
      )}
      {question && (
        <Modal
          title="Answer this question"
          description="Your answer is saved as a human-provided update, not as transcript evidence."
          onClose={() => !busy && setQuestion(null)}
        >
          <form onSubmit={saveAnswer} className="modal-form">
            <p className="question-prompt">{question.text}</p>
            <Field label="Your answer" required>
              <textarea
                rows={5}
                required
                maxLength={5000}
                value={answer}
                onChange={(event) => setAnswer(event.target.value)}
              />
            </Field>
            <div className="modal-actions">
              <Button
                type="button"
                variant="secondary"
                onClick={() => setQuestion(null)}
                disabled={!!busy}
              >
                Cancel
              </Button>
              <Button type="submit" busy={busy === question.id}>
                Save answer
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
