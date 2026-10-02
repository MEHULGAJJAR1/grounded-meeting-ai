import { useEffect, useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import {
  ArrowRight,
  Check,
  Eye,
  EyeOff,
  FileText,
  ListTodo,
  LockKeyhole,
  Quote,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { api, errorMessage } from "../services/api";
import { Brand, Button, Field } from "../components/UI";

export default function AuthPage({ register = false }) {
  const auth = useAuth();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [demoEnabled, setDemoEnabled] = useState(false);
  useEffect(() => {
    api
      .get("/health")
      .then(({ data }) => setDemoEnabled(data.demo_enabled))
      .catch(() => {});
  }, []);
  if (auth.user && !(register && auth.user.is_demo))
    return <Navigate to="/dashboard" replace />;
  async function submit(event) {
    event.preventDefault();
    setBusy("auth");
    setError("");
    try {
      if (register)
        await auth.register({
          name,
          email,
          password,
          timezone:
            Intl.DateTimeFormat().resolvedOptions().timeZone || "Asia/Kolkata",
        });
      else await auth.login({ email, password });
      navigate("/dashboard");
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      setBusy("");
    }
  }
  async function demo() {
    setBusy("demo");
    setError("");
    try {
      await auth.demo();
      navigate("/dashboard");
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      setBusy("");
    }
  }
  return (
    <div className="auth-page">
      <div className="auth-story">
        <Brand inverse />
        <div className="auth-story-content">
          <div className="auth-eyebrow">
            <span />
            MEETING INTELLIGENCE, GROUNDED IN FACT
          </div>
          <h1>
            Good conversations.
            <br />
            Clear decisions.
            <br />
            <em>Real follow-through.</em>
          </h1>
          <p>
            Turn the messy parts of your meetings into source-backed insights
            and actions that actually move work forward.
          </p>
          <div className="auth-illustration" aria-hidden="true">
            <div className="illustration-line" />
            <div className="source-note">
              <div className="note-label">
                <FileText size={14} />
                THE CONVERSATION
              </div>
              <div className="note-lines">
                <i />
                <i />
                <i />
                <i />
              </div>
              <span className="source-highlight">
                “I'll own the rollout plan.”
              </span>
            </div>
            <div className="grounding-node">
              <ShieldCheck size={29} />
            </div>
            <div className="action-note">
              <div className="note-label">
                <ListTodo size={14} />
                THE CLARITY
              </div>
              <div className="illustration-task">
                <span>
                  <Check size={12} />
                </span>
                Rollout plan
              </div>
              <div className="note-lines">
                <i />
                <i />
              </div>
              <div className="verified-note">
                <ShieldCheck size={12} />
                Source verified
              </div>
            </div>
          </div>
          <div className="auth-feature-row">
            <span>
              <Quote size={15} />
              Traceable evidence
            </span>
            <span>
              <LockKeyhole size={15} />
              Private by design
            </span>
          </div>
        </div>
        <div className="auth-story-footer">
          Less ambiguity. More accountability.
        </div>
      </div>
      <div className="auth-form-panel">
        <div className="auth-top-link">
          {register ? "Already have an account?" : "New to Grounded?"}{" "}
          <Link to={register ? "/login" : "/register"}>
            {register ? "Sign in" : "Create an account"}{" "}
            <ArrowRight size={13} />
          </Link>
        </div>
        <div className="auth-form-container">
          <div className="mobile-brand">
            <Brand />
          </div>
          <span className="auth-form-icon">
            <ShieldCheck size={25} />
          </span>
          <h2>{register ? "Make room for clarity." : "Welcome back."}</h2>
          <p>
            {register
              ? "Your next meeting deserves more than a wall of notes."
              : "Your meetings, decisions and next steps. All in one place."}
          </p>
          <form onSubmit={submit}>
            {register && (
              <Field label="Full name" required>
                <input
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  required
                  minLength={2}
                  maxLength={120}
                  autoComplete="name"
                  placeholder="Your full name"
                />
              </Field>
            )}
            <Field label="Email address" required>
              <input
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                required
                autoComplete="email"
                placeholder="you@company.com"
              />
            </Field>
            <Field
              label="Password"
              required
              hint={
                register
                  ? "10–72 characters, with at least one letter and one number."
                  : "Sessions are private and protected with JWT authentication."
              }
            >
              <div className="password-field">
                <input
                  type={show ? "text" : "password"}
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  required
                  minLength={register ? 10 : 1}
                  maxLength={72}
                  autoComplete={register ? "new-password" : "current-password"}
                  placeholder={
                    register
                      ? "Choose a strong password"
                      : "Enter your password"
                  }
                />
                <button
                  type="button"
                  className="icon-btn"
                  aria-label={show ? "Hide password" : "Show password"}
                  onClick={() => setShow(!show)}
                >
                  {show ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </Field>
            {error && (
              <div className="form-error" role="alert">
                {error}
              </div>
            )}
            <Button
              className="full-width"
              busy={busy === "auth"}
              disabled={!!busy}
              type="submit"
            >
              {register ? "Create account" : "Sign in"}
              <ArrowRight size={17} />
            </Button>
          </form>
          {demoEnabled && !register && (
            <>
              <div className="auth-divider">
                <span>or explore before you commit</span>
              </div>
              <Button
                variant="secondary"
                className="full-width"
                icon={Sparkles}
                busy={busy === "demo"}
                disabled={!!busy}
                onClick={demo}
              >
                {busy === "demo"
                  ? "Preparing your isolated workspace…"
                  : "Explore sample workspace"}
              </Button>
              <small className="auth-demo-note">
                Development only · five labelled sample meetings.
                <br />A real, private workspace — no shared account.
              </small>
            </>
          )}
          <div className="auth-security">
            <LockKeyhole size={13} />
            Your data stays in your own workspace.
          </div>
        </div>
        <div className="auth-bottom">
          Grounded AI Meeting Notes Summariser & Action Tracker
        </div>
      </div>
    </div>
  );
}
