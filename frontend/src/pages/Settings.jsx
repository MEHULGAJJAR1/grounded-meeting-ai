import { useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowUpRight,
  Bell,
  BookOpen,
  KeyRound,
  LockKeyhole,
  Save,
  ShieldCheck,
  Sparkles,
  UserRound,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { useResource } from "../hooks/useResource";
import { api, errorMessage } from "../services/api";
import { dateLabel, fileSize } from "../services/format";
import {
  Avatar,
  Badge,
  Button,
  Field,
  PageHeading,
  Skeleton,
} from "../components/UI";

export default function Settings() {
  const { user, setUser, configuration, logout } = useAuth();
  const toast = useToast();
  const audits = useResource("/audit-log");
  const [profile, setProfile] = useState({
    name: user.name,
    timezone: user.timezone,
    notifications_enabled: user.notifications_enabled,
  });
  const [password, setPassword] = useState({
    current_password: "",
    new_password: "",
    confirm: "",
  });
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  async function save(event) {
    event.preventDefault();
    setBusy("profile");
    setError("");
    try {
      const { data } = await api.put("/auth/me", profile);
      setUser(data);
      audits.reload();
      toast("Profile and notification preferences saved.");
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      setBusy("");
    }
  }
  async function changePassword(event) {
    event.preventDefault();
    if (password.new_password !== password.confirm) {
      toast("New passwords do not match.", "error");
      return;
    }
    setBusy("password");
    try {
      await api.put("/auth/password", {
        current_password: password.current_password,
        new_password: password.new_password,
      });
      toast(
        "Password changed. All existing sessions are invalidated. Please sign in again.",
      );
      await logout(false);
    } catch (failure) {
      toast(errorMessage(failure), "error");
    } finally {
      setBusy("");
    }
  }
  async function seed() {
    setBusy("seed");
    try {
      const { data } = await api.post("/dev/demo-data");
      audits.reload();
      toast(
        data.created
          ? `${data.created} fictional sample meetings loaded and processed.`
          : "Your sample meetings are already loaded. No duplicates created.",
      );
    } catch (failure) {
      toast(errorMessage(failure), "error");
    } finally {
      setBusy("");
    }
  }
  return (
    <div className="page settings-page">
      <PageHeading
        eyebrow="MAKE IT YOUR WORKSPACE"
        title="Settings & profile"
        description="Your account, processing configuration and traceable activity."
      />
      <div className="settings-grid">
        <section className="card settings-card">
          <div className="settings-card-heading">
            <UserRound size={20} />
            <h2>Your profile</h2>
          </div>
          <div className="profile-summary">
            <Avatar name={user.name} />
            <div>
              <strong>{user.name}</strong>
              <span>{user.email}</span>
              <small>
                Member since {dateLabel(user.created_at, { year: "numeric" })}
              </small>
            </div>
          </div>
          <form onSubmit={save}>
            <Field label="Full name" required>
              <input
                required
                minLength={2}
                maxLength={120}
                value={profile.name}
                onChange={(event) =>
                  setProfile({ ...profile, name: event.target.value })
                }
              />
            </Field>
            <Field
              label="Timezone"
              hint="Calendar deadlines and overdue checks use this timezone."
            >
              <input
                required
                list="timezones"
                value={profile.timezone}
                onChange={(event) =>
                  setProfile({ ...profile, timezone: event.target.value })
                }
              />
              <datalist id="timezones">
                {[
                  "Asia/Kolkata",
                  "UTC",
                  "Europe/London",
                  "Europe/Paris",
                  "America/New_York",
                  "America/Los_Angeles",
                  "Asia/Singapore",
                  "Australia/Sydney",
                ].map((zone) => (
                  <option key={zone} value={zone} />
                ))}
              </datalist>
            </Field>
            <label className="notification-toggle">
              <span>
                <Bell size={18} />
                <span>
                  <strong>Deadline & processing reminders</strong>
                  <small>
                    In-app notifications; SMTP email only if configured.
                  </small>
                </span>
              </span>
              <input
                type="checkbox"
                className="switch-input"
                checked={profile.notifications_enabled}
                onChange={(event) =>
                  setProfile({
                    ...profile,
                    notifications_enabled: event.target.checked,
                  })
                }
              />
            </label>
            {error && (
              <p className="form-error" role="alert">
                {error}
              </p>
            )}
            <Button type="submit" icon={Save} busy={busy === "profile"}>
              Save changes
            </Button>
          </form>
        </section>
        <section className="card settings-card" id="ai">
          <div className="settings-card-heading">
            <Sparkles size={20} />
            <h2>AI & grounding configuration</h2>
          </div>
          <div className="configuration-status">
            <span className="mode-dot" />
            <strong>
              {configuration?.provider === "openai"
                ? "OpenAI configured"
                : "Local extractive mode"}
            </strong>
            <Badge value={configuration?.environment || "development"} />
          </div>
          <dl className="config-list">
            <div>
              <dt>Extraction model</dt>
              <dd>{configuration?.model || "Loading…"}</dd>
            </div>
            <div>
              <dt>Embedding model</dt>
              <dd>{configuration?.embedding_model || "Loading…"}</dd>
            </div>
            <div>
              <dt>Upload limit</dt>
              <dd>{fileSize(configuration?.max_upload_size || 10485760)}</dd>
            </div>
            <div>
              <dt>Email delivery</dt>
              <dd>
                {configuration?.smtp_configured
                  ? "SMTP configured"
                  : "In-app notifications only"}
              </dd>
            </div>
            <div>
              <dt>Session lifetime</dt>
              <dd>{configuration?.token_lifetime_minutes || 120} minutes</dd>
            </div>
          </dl>
          <div className="settings-grounding-note">
            <ShieldCheck size={20} />
            <div>
              <strong>Grounding is a separate verification step.</strong>
              <p>
                Exact quotes are checked against the source. OpenAI mode
                independently checks entailment. Unsupported metadata is reset;
                unsupported claims are withheld. Confidence is heuristic, not a
                guarantee.
              </p>
            </div>
          </div>
          <p className="settings-env-note">
            Configure models, OpenAI and SMTP using the repository’s{" "}
            <code>.env</code> file, then restart the backend. API keys never
            enter the browser.
          </p>
          <a
            href="/api/docs"
            target="_blank"
            rel="noreferrer"
            className="text-btn"
          >
            Explore API documentation <ArrowUpRight size={14} />
          </a>
        </section>
        <section className="card settings-card">
          <div className="settings-card-heading">
            <KeyRound size={20} />
            <h2>Password & sessions</h2>
          </div>
          <p className="settings-description">
            Passwords are bcrypt-hashed. Changing your password invalidates all
            current JWT sessions.
          </p>
          <form onSubmit={changePassword}>
            <Field label="Current password" required>
              <input
                type="password"
                required
                value={password.current_password}
                autoComplete="current-password"
                onChange={(event) =>
                  setPassword({
                    ...password,
                    current_password: event.target.value,
                  })
                }
              />
            </Field>
            <Field
              label="New password"
              required
              hint="10–72 characters, with at least one letter and one number."
            >
              <input
                type="password"
                required
                minLength={10}
                maxLength={72}
                autoComplete="new-password"
                value={password.new_password}
                onChange={(event) =>
                  setPassword({ ...password, new_password: event.target.value })
                }
              />
            </Field>
            <Field label="Confirm new password" required>
              <input
                type="password"
                required
                minLength={10}
                maxLength={72}
                autoComplete="new-password"
                value={password.confirm}
                onChange={(event) =>
                  setPassword({ ...password, confirm: event.target.value })
                }
              />
            </Field>
            <Button
              variant="secondary"
              icon={LockKeyhole}
              type="submit"
              busy={busy === "password"}
            >
              Update password
            </Button>
          </form>
        </section>
        <section className="card settings-card">
          <div className="settings-card-heading">
            <BookOpen size={20} />
            <h2>Workspace & sample data</h2>
          </div>
          <p className="settings-description">
            Your meetings, action records, documents, retrieval index and audit
            trail are isolated by authenticated user ID.
          </p>
          <ul className="privacy-list">
            <li>
              <ShieldCheck size={15} />
              No cross-user retrieval or document access.
            </li>
            <li>
              <ShieldCheck size={15} />
              Tokens are stored in this tab’s session storage.
            </li>
            <li>
              <ShieldCheck size={15} />
              Chat exchanges are not persisted by the server.
            </li>
            <li>
              <ShieldCheck size={15} />
              Transcript text and passwords are excluded from application logs.
            </li>
          </ul>
          {configuration?.demo_enabled && (
            <div className="development-data">
              <Badge value="development">Development only</Badge>
              <h3>Explore the full pipeline</h3>
              <p>
                Load five clearly labelled fictional meetings with decisions,
                deadlines, risks and working action records. Samples use the
                real local extractive pipeline, avoiding paid AI calls.
              </p>
              <Button
                variant="secondary"
                icon={Sparkles}
                busy={busy === "seed"}
                onClick={seed}
              >
                Load demo data
              </Button>
            </div>
          )}
          <Link className="text-btn" to="/meetings">
            Manage your meetings <ArrowUpRight size={14} />
          </Link>
        </section>
      </div>
      <section className="card audit-card">
        <div className="card-heading">
          <div>
            <h2>Activity & audit trail</h2>
            <p>
              The latest 50 changes in your workspace · no transcript content
              logged
            </p>
          </div>
          <Button variant="ghost" onClick={audits.reload}>
            Refresh activity
          </Button>
        </div>
        {audits.loading ? (
          <Skeleton height={140} />
        ) : audits.error ? (
          <p className="form-error">{audits.error}</p>
        ) : (
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Activity</th>
                  <th>Entity</th>
                  <th>When</th>
                </tr>
              </thead>
              <tbody>
                {audits.data?.items.map((entry) => (
                  <tr key={entry.id}>
                    <td data-label="Activity">
                      {entry.action.replaceAll(".", " · ").replaceAll("_", " ")}
                    </td>
                    <td data-label="Entity">
                      <code>
                        {entry.entity_type} · {entry.entity_id.slice(0, 8)}
                      </code>
                    </td>
                    <td data-label="When">
                      {dateLabel(entry.created_at, {
                        hour: "2-digit",
                        minute: "2-digit",
                        timeZone: user.timezone,
                      })}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
