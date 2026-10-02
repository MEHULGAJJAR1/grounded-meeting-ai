import DashboardCharts from "../components/DashboardCharts";
import { useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  ArrowUpRight,
  CalendarDays,
  CheckCircle2,
  CircleHelp,
  Clock3,
  ListTodo,
  Plus,
  ShieldCheck,
  Sparkles,
  Target,
  TriangleAlert,
  UserRound,
} from "lucide-react";
import { useResource } from "../hooks/useResource";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { api, errorMessage } from "../services/api";
import { dateLabel, isOverdue } from "../services/format";
import {
  Avatar,
  Badge,
  Button,
  EmptyState,
  ErrorState,
  PageHeading,
  PageSkeleton,
} from "../components/UI";

const METRICS = [
  [
    "total_meetings",
    "Total meetings",
    CalendarDays,
    "mint",
    "/meetings",
    "Your meeting history",
  ],
  [
    "total_action_items",
    "Action items",
    ListTodo,
    "purple",
    "/actions",
    "Extracted + user created",
  ],
  [
    "pending_actions",
    "Pending actions",
    Clock3,
    "amber",
    "/actions?filter=Pending",
    "Ready for a next step",
  ],
  [
    "completed_actions",
    "Completed actions",
    CheckCircle2,
    "blue",
    "/actions?filter=Completed",
    "Follow-through in motion",
  ],
  [
    "unassigned_actions",
    "Unassigned actions",
    UserRound,
    "purple",
    "/actions?filter=Unassigned",
    "Needs a clear owner",
  ],
  [
    "upcoming_deadlines",
    "Upcoming deadlines",
    Target,
    "mint",
    "/actions",
    "Within the next 7 days",
  ],
  [
    "open_risks",
    "Open risks",
    TriangleAlert,
    "amber",
    "/search?q=Show%20unresolved%20risks",
    "Worth keeping an eye on",
  ],
  [
    "unanswered_questions",
    "Open questions",
    CircleHelp,
    "blue",
    "/search?q=Show%20unanswered%20questions",
    "Waiting for clarity",
  ],
];

export default function Dashboard() {
  const stats = useResource("/dashboard/stats");
  const charts = useResource("/dashboard/charts");
  const { user, configuration } = useAuth();
  const toast = useToast();
  const [seeding, setSeeding] = useState(false);
  if (stats.loading && !stats.data) return <PageSkeleton />;
  if (stats.error)
    return (
      <div className="page">
        <ErrorState message={stats.error} onRetry={stats.reload} />
      </div>
    );
  if (!stats.data) return null;
  const data = stats.data;
  const chartData = charts.data;
  const completion = data.total_action_items
    ? Math.round((100 * data.completed_actions) / data.total_action_items)
    : 0;
  async function loadDemo() {
    setSeeding(true);
    try {
      await api.post("/dev/demo-data");
      stats.reload();
      charts.reload();
      toast("Sample meetings loaded and processed with the real local engine.");
    } catch (error) {
      toast(errorMessage(error), "error");
    } finally {
      setSeeding(false);
    }
  }
  return (
    <div className="page dashboard-page">
      <PageHeading
        eyebrow="YOUR WORKSPACE, AT A GLANCE"
        title={`A clearer picture, ${user.name.split(" ")[0]}.`}
        description="Keep the conversation. Lose the ambiguity."
      >
        <span className="date-chip">
          <CalendarDays size={15} />
          {dateLabel(data.today, { year: "numeric" })}
        </span>
        <Link to="/meetings/new" className="btn btn-primary">
          <Plus size={17} />
          New meeting
        </Link>
      </PageHeading>
      <div className="intelligence-banner">
        <div className="banner-shield">
          <ShieldCheck size={26} />
        </div>
        <div>
          <div className="banner-eyebrow">GROUNDED BY DESIGN</div>
          <h3>Every insight comes with a paper trail.</h3>
          <p>Source-backed summaries. Clear owners. No invented deadlines.</p>
        </div>
        <Link to="/assistant" className="banner-link">
          Ask your meetings <ArrowUpRight size={17} />
        </Link>
        <div className="banner-decoration" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
      </div>
      <div className="metric-grid">
        {METRICS.map(([key, label, Icon, color, url, note]) => (
          <Link to={url} className="metric-card" key={key}>
            <div className="metric-top">
              <span>{label}</span>
              <span className={`metric-icon ${color}`}>
                <Icon size={18} />
              </span>
            </div>
            <strong>{data[key]}</strong>
            <div className="metric-note">
              {key === "completed_actions" && data.total_action_items > 0 ? (
                <>
                  <span className="positive">{completion}%</span> of all actions
                  completed
                </>
              ) : (
                note
              )}
            </div>
          </Link>
        ))}
      </div>
      {!data.total_meetings ? (
        <div className="card onboarding-card">
          <EmptyState
            icon={CalendarDays}
            title="Clarity starts with your first meeting."
            description="Paste a transcript or upload a document. We’ll organise the decisions, next steps and the evidence behind them."
          >
            <Link to="/meetings/new" className="btn btn-primary">
              <Plus size={16} />
              Create a meeting
            </Link>
            {configuration?.demo_enabled && (
              <Button
                variant="secondary"
                icon={Sparkles}
                busy={seeding}
                onClick={loadDemo}
              >
                Load sample meetings
              </Button>
            )}
          </EmptyState>
        </div>
      ) : (
        <>
          {charts.error ? (
            <ErrorState message={charts.error} onRetry={charts.reload} />
          ) : (
            chartData && (
              <>
                <DashboardCharts chartData={chartData} data={data} />
              </>
            )
          )}
          <div className="dashboard-bottom-grid">
            <section className="card recent-meetings">
              <div className="card-heading">
                <div>
                  <h2>Recent meetings</h2>
                  <p>The latest conversations in your workspace</p>
                </div>
                <Link to="/meetings" className="text-btn">
                  View all <ArrowRight size={14} />
                </Link>
              </div>
              <div className="meeting-mini-list">
                {data.recent_meetings.map((meeting, index) => (
                  <Link
                    className="meeting-mini"
                    to={`/meetings/${meeting.id}`}
                    key={meeting.id}
                  >
                    <span className={`meeting-mini-icon color-${index % 4}`}>
                      <CalendarDays size={19} />
                    </span>
                    <div className="mini-text">
                      <h3>{meeting.title}</h3>
                      <span>
                        {dateLabel(meeting.date)}
                        <i />
                        {meeting.project || meeting.meeting_type}
                      </span>
                    </div>
                    <div className="mini-actions-count">
                      <ListTodo size={13} />
                      {meeting.action_count}
                    </div>
                    <Badge value={meeting.processing_status}>
                      {meeting.processing_status === "completed"
                        ? "Analysed"
                        : meeting.processing_status}
                    </Badge>
                    <ChevronArrow />
                  </Link>
                ))}
              </div>
            </section>
            <section className="card deadline-watch">
              <div className="card-heading">
                <div>
                  <h2>Deadline watch</h2>
                  <p>Keep the next steps moving</p>
                </div>
                <Clock3 size={18} className="muted" />
              </div>
              {!data.deadline_items.length ? (
                <EmptyState
                  compact
                  icon={CheckCircle2}
                  title="No dated tasks waiting"
                  description="Explicit calendar deadlines will appear here."
                />
              ) : (
                <div className="deadline-list">
                  {data.deadline_items.slice(0, 4).map((item) => (
                    <Link
                      to={`/actions?q=${encodeURIComponent(item.task.slice(0, 80))}`}
                      className="deadline-item"
                      key={item.id}
                    >
                      <span
                        className={`deadline-date ${isOverdue(item, data.today) ? "overdue" : ""}`}
                      >
                        <strong>{item.due_date.slice(8)}</strong>
                        {dateLabel(item.due_date, { day: undefined })}
                      </span>
                      <div>
                        <h3>{item.task.replace(/^Action:\s*/, "")}</h3>
                        <span>
                          <Avatar name={item.owner} small />
                          {item.owner}
                          <i />
                          {isOverdue(item, data.today) ? "Overdue" : "Upcoming"}
                        </span>
                      </div>
                    </Link>
                  ))}
                </div>
              )}
              <Link to="/actions" className="deadline-footer">
                Open action tracker <ArrowRight size={14} />
              </Link>
            </section>
          </div>
          <p className="dashboard-footnote">
            <ShieldCheck size={12} />
            Counts describe your current records, including clearly labelled
            review candidates. They are not an inferred meeting quality score.
          </p>
        </>
      )}
    </div>
  );
}
function ChevronArrow() {
  return <ArrowUpRight size={16} className="muted mini-arrow" />;
}
