import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  ArrowRight,
  ArrowUpRight,
  CheckCircle2,
  Copy,
  Database,
  FileText,
  LoaderCircle,
  MessageSquareText,
  Plus,
  RefreshCw,
  Send,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { useResource } from "../hooks/useResource";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { api, copyText, errorMessage } from "../services/api";
import { dateLabel } from "../services/format";
import {
  Avatar,
  Button,
  EmptyState,
  Field,
  PageHeading,
} from "../components/UI";
import Sources from "../components/Sources";

const PROMPTS = [
  ["Catch up quickly", "Summarise my last sprint meeting.", FileText],
  ["Find your next step", "What tasks are assigned to me?", CheckCircle2],
  ["Keep an eye on risks", "Show unresolved risks.", ShieldCheck],
  [
    "Trace a decision",
    "Which decisions were made about the dashboard?",
    MessageSquareText,
  ],
];
export default function Assistant() {
  const { user, configuration } = useAuth();
  const toast = useToast();
  const [params] = useSearchParams();
  const stats = useResource("/dashboard/stats");
  const meetings = useResource("/meetings?limit=100");
  const [messages, setMessages] = useState([]);
  const [query, setQuery] = useState("");
  const [scope, setScope] = useState("");
  const [pending, setPending] = useState(false);
  const end = useRef(null);
  const initialSent = useRef(false);
  useEffect(() => {
    if (params.get("q") && !initialSent.current) {
      initialSent.current = true;
      send(params.get("q"));
    }
  }, []);
  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [messages, pending]);
  async function send(value = query) {
    const question = value.trim();
    if (question.length < 2 || pending) return;
    const history = messages.slice(-10).map((message) => ({
      role: message.role,
      content: (message.role === "user"
        ? message.content
        : [
            message.result?.answer,
            ...(message.result?.claims || []).map((c) => c.text),
          ].join("\n")
      ).slice(0, 4000),
    }));
    setMessages((old) => [
      ...old,
      { role: "user", content: question, id: `${Date.now()}-user` },
    ]);
    setQuery("");
    setPending(true);
    try {
      const { data } = await api.post("/ask", {
        query: question,
        limit: 10,
        meeting_id: scope || null,
        history,
      });
      setMessages((old) => [
        ...old,
        { role: "assistant", result: data, id: `${Date.now()}-answer` },
      ]);
    } catch (error) {
      setMessages((old) => [
        ...old,
        {
          role: "assistant",
          error: errorMessage(error),
          id: `${Date.now()}-error`,
        },
      ]);
    } finally {
      setPending(false);
    }
  }
  async function copy(result) {
    try {
      await copyText(
        [result.answer, ...result.claims.map((c) => c.text)].join("\n\n"),
      );
      toast("Answer copied.");
    } catch (error) {
      toast(error.message, "error");
    }
  }
  return (
    <div className="page assistant-page">
      <PageHeading
        eyebrow="YOUR HISTORY. YOUR ANSWERS."
        title="The grounded assistant"
        description="Ask your meetings a question. Get an answer with evidence."
      >
        <Button
          variant="secondary"
          icon={Plus}
          disabled={pending || !messages.length}
          onClick={() => setMessages([])}
        >
          New conversation
        </Button>
      </PageHeading>
      <div className="assistant-grid">
        <section className="card assistant-chat">
          <div className="chat-header">
            <span className="chat-avatar">
              <Sparkles size={17} />
            </span>
            <div>
              <h3>Grounded intelligence</h3>
              <small>Retrieval first. Evidence always.</small>
            </div>
            <span className="chat-private">
              <ShieldCheck size={13} />
              Private
            </span>
          </div>
          <div className="conversation" aria-live="polite">
            {!messages.length ? (
              <div className="assistant-welcome">
                <span className="assistant-welcome-icon">
                  <Sparkles size={31} />
                </span>
                <div className="eyebrow">ANSWERS WITH A PAPER TRAIL</div>
                <h2>What’s on your mind?</h2>
                <p>
                  Connect the dots across meetings, follow up on commitments and
                  find the original conversation.
                </p>
                <div className="prompt-grid">
                  {PROMPTS.map(([title, prompt, Icon]) => (
                    <button
                      key={prompt}
                      onClick={() => send(prompt)}
                      disabled={pending}
                    >
                      <Icon size={19} />
                      <strong>{title}</strong>
                      <span>{prompt}</span>
                      <ArrowUpRight size={15} />
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <div className="chat-messages">
                {messages.map((message) =>
                  message.role === "user" ? (
                    <div className="chat-message user-message" key={message.id}>
                      <Avatar name={user.name} small />
                      <div>
                        <div className="message-label">You</div>
                        <p>{message.content}</p>
                      </div>
                    </div>
                  ) : (
                    <div
                      className="chat-message assistant-message"
                      key={message.id}
                    >
                      <span className="chat-avatar">
                        <Sparkles size={15} />
                      </span>
                      <div className="assistant-message-body">
                        <div className="message-label">
                          Grounded
                          <span>
                            {message.result?.provider || "Request error"}
                          </span>
                        </div>
                        {message.error ? (
                          <div className="form-error" role="alert">
                            {message.error}
                            <button
                              className="text-btn"
                              onClick={() =>
                                send(
                                  messages[
                                    Math.max(
                                      0,
                                      messages.findIndex(
                                        (m) => m.id === message.id,
                                      ) - 1,
                                    )
                                  ]?.content,
                                )
                              }
                              disabled={pending}
                            >
                              Retry question <RefreshCw size={12} />
                            </button>
                          </div>
                        ) : (
                          <>
                            <p className="answer-intro">
                              {message.result.answer}
                            </p>
                            <div className="answer-claims">
                              {message.result.claims.map((claim, index) => (
                                <div className="answer-claim" key={index}>
                                  <p>{claim.text}</p>
                                  {claim.grounding_status ===
                                    "user_provided" && (
                                    <small className="muted">
                                      Current user-provided record, not a
                                      transcript assertion
                                    </small>
                                  )}
                                  <div className="inline-citations">
                                    {claim.source_ids.map((sourceId) => {
                                      const sourceIndex =
                                        message.result.sources.findIndex(
                                          (source) => source.id === sourceId,
                                        );
                                      const source =
                                        message.result.sources[sourceIndex];
                                      return source ? (
                                        <Link
                                          key={sourceId}
                                          to={`/meetings/${source.meeting_id}?line=${source.evidence[0]?.line_start || 1}`}
                                          title={source.meeting_title}
                                        >
                                          <FileText size={10} />
                                          {sourceIndex + 1}
                                        </Link>
                                      ) : null;
                                    })}
                                  </div>
                                </div>
                              ))}
                            </div>
                            {message.result.note && (
                              <p className="answer-note">
                                {message.result.note}
                              </p>
                            )}
                            <Sources
                              sources={message.result.sources}
                              claims={message.result.claims}
                            />
                            <div className="message-bottom">
                              <span>
                                <ShieldCheck size={12} />
                                {
                                  message.result.grounding.verified
                                } verified{" "}
                                {message.result.grounding.withheld
                                  ? `· ${message.result.grounding.withheld} withheld`
                                  : ""}
                              </span>
                              <button
                                className="text-btn"
                                aria-label="Copy answer"
                                onClick={() => copy(message.result)}
                              >
                                <Copy size={13} />
                                Copy
                              </button>
                            </div>
                          </>
                        )}
                      </div>
                    </div>
                  ),
                )}
              </div>
            )}
            {pending && (
              <div className="assistant-pending" role="status">
                <LoaderCircle size={17} className="spin" />
                <span>Retrieving sources and verifying an answer…</span>
              </div>
            )}
            <div ref={end} />
          </div>
          <div className="chat-composer-area">
            <form
              className="chat-composer"
              onSubmit={(event) => {
                event.preventDefault();
                send();
              }}
            >
              <textarea
                aria-label="Ask about your meeting history"
                placeholder="Ask about your meetings, tasks or decisions…"
                rows={2}
                value={query}
                maxLength={2000}
                disabled={pending}
                onChange={(event) => setQuery(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    send();
                  }
                }}
              />
              <Button
                type="submit"
                aria-label="Send question"
                disabled={pending || query.trim().length < 2}
                busy={pending}
              >
                <Send size={17} />
              </Button>
            </form>
            <div className="composer-note">
              <span>
                <ShieldCheck size={12} />
                No evidence? No invented answer.
              </span>
              <span>Enter to send · Shift + Enter for a new line</span>
            </div>
          </div>
        </section>
        <aside className="assistant-context">
          <div className="card knowledge-card">
            <div className="knowledge-card-header">
              <span>
                <Database size={19} />
              </span>
              <h3>Your knowledge base</h3>
              <button
                className="icon-btn"
                aria-label="Refresh meeting context"
                onClick={() => {
                  stats.reload();
                  meetings.reload();
                }}
              >
                <RefreshCw size={15} />
              </button>
            </div>
            <p>
              Context comes only from your own processed meetings and current
              records.
            </p>
            <div className="knowledge-numbers">
              <div>
                <strong>
                  {stats.loading ? "—" : (stats.data?.total_meetings ?? 0)}
                </strong>
                <span>meetings</span>
              </div>
              <div>
                <strong>
                  {stats.loading ? "—" : (stats.data?.total_action_items ?? 0)}
                </strong>
                <span>action items</span>
              </div>
            </div>
            <Field label="Answer scope">
              <select
                value={scope}
                onChange={(event) => setScope(event.target.value)}
                disabled={pending}
              >
                <option value="">All my meetings</option>
                {meetings.data?.items.map((m) => (
                  <option value={m.id} key={m.id}>
                    {m.title}
                  </option>
                ))}
              </select>
            </Field>
            <div className="knowledge-mode">
              <span className="mode-dot" />
              <span>
                {configuration?.provider === "openai"
                  ? "OpenAI synthesis + verification"
                  : "Local extractive answers"}
              </span>
            </div>
            {configuration?.provider !== "openai" && (
              <p className="knowledge-mode-help">
                Local mode returns real source excerpts. Add your OpenAI key to
                .env for LLM synthesis and neural semantic retrieval.
              </p>
            )}
          </div>
          <div className="card context-meetings">
            <h3>Recent conversations</h3>
            {stats.data?.recent_meetings.length ? (
              stats.data.recent_meetings.map((m) => (
                <Link key={m.id} to={`/meetings/${m.id}`}>
                  <FileText size={16} />
                  <span>
                    <strong>{m.title}</strong>
                    <small>
                      {dateLabel(m.date)} · {m.project}
                    </small>
                  </span>
                  <ArrowUpRight size={13} />
                </Link>
              ))
            ) : (
              <EmptyState
                compact
                icon={FileText}
                title="No meeting history yet"
                description="Create a meeting to build your evidence base."
              />
            )}
            <Link to="/meetings" className="text-btn">
              View your meetings <ArrowRight size={14} />
            </Link>
          </div>
          <div className="assistant-safety">
            <ShieldCheck size={23} />
            <h4>Trust, but trace.</h4>
            <p>
              Sources and exact evidence are attached to answers. Unsupported
              claims are withheld. Scores describe support, not certainty.
            </p>
          </div>
        </aside>
      </div>
    </div>
  );
}
