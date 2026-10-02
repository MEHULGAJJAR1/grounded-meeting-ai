import {
  Children,
  cloneElement,
  isValidElement,
  useEffect,
  useId,
  useRef,
} from "react";
import {
  AlertCircle,
  ChevronDown,
  LoaderCircle,
  ShieldCheck,
  X,
  Layers,
} from "lucide-react";
import { Link } from "react-router-dom";
import { initials, slug } from "../services/format";

export function Brand({ compact = false, inverse = false }) {
  return (
    <Link
      to="/dashboard"
      className={`brand ${inverse ? "inverse" : ""}`}
      aria-label="Grounded home"
    >
      <span className="brand-symbol">
        <Layers size={23} strokeWidth={2.3} />
      </span>
      {!compact && (
        <span>
          grounded<span className="brand-period">.</span>
        </span>
      )}
    </Link>
  );
}
export function Button({
  children,
  variant = "primary",
  busy = false,
  icon: Icon,
  className = "",
  disabled = false,
  ...props
}) {
  return (
    <button
      className={`btn btn-${variant} ${className}`}
      disabled={busy || disabled}
      {...props}
    >
      {busy ? (
        <LoaderCircle className="spin" size={17} />
      ) : Icon ? (
        <Icon size={17} />
      ) : null}
      {children}
    </button>
  );
}
export function Badge({ children, value, className = "", ...props }) {
  return (
    <span
      className={`badge badge-${slug(value || children)} ${className}`}
      {...props}
    >
      {children || value}
    </span>
  );
}
export function Avatar({ name, index = 0, small = false }) {
  return (
    <span
      title={name}
      className={`avatar avatar-${index % 5} ${small ? "small" : ""}`}
    >
      {initials(name)}
    </span>
  );
}
export function AvatarGroup({ names = [] }) {
  return (
    <div className="avatar-group">
      {names.slice(0, 4).map((name, index) => (
        <Avatar name={name} index={index} small key={name} />
      ))}
      {names.length > 4 && (
        <span className="avatar small more">+{names.length - 4}</span>
      )}
    </div>
  );
}
export function PageHeading({ eyebrow, title, description, children }) {
  return (
    <div className="page-heading">
      <div>
        {eyebrow && <div className="eyebrow">{eyebrow}</div>}
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      <div className="heading-actions">{children}</div>
    </div>
  );
}
export function Field({
  label,
  hint,
  children,
  className = "",
  required = false,
}) {
  const generatedId = useId();
  let controlId = `field-${generatedId.replaceAll(":", "")}`;
  let assigned = false;
  function associate(node) {
    if (!isValidElement(node)) return node;
    if (!assigned && ["input", "select", "textarea"].includes(node.type)) {
      assigned = true;
      controlId = node.props.id || controlId;
      return cloneElement(node, {
        id: controlId,
        required: node.props.required ?? required,
        "aria-describedby": hint
          ? [node.props["aria-describedby"], `${controlId}-hint`]
              .filter(Boolean)
              .join(" ")
          : node.props["aria-describedby"],
      });
    }
    return node.props.children
      ? cloneElement(node, {}, Children.map(node.props.children, associate))
      : node;
  }
  const controls = Children.map(children, associate);
  return (
    <div className={`field ${className}`}>
      <label className="field-label" htmlFor={controlId}>
        {label}
        {required && (
          <span className="required" aria-hidden="true">
            *
          </span>
        )}
      </label>
      {controls}
      {hint && (
        <span className="field-hint" id={`${controlId}-hint`}>
          {hint}
        </span>
      )}
    </div>
  );
}
export function EmptyState({
  icon: Icon = Layers,
  title,
  description,
  children,
  compact = false,
}) {
  return (
    <div className={`empty-state ${compact ? "compact" : ""}`}>
      <span className="empty-icon">
        <Icon size={27} />
      </span>
      <h3>{title}</h3>
      <p>{description}</p>
      <div className="empty-actions">{children}</div>
    </div>
  );
}
export function ErrorState({ message, onRetry }) {
  return (
    <div className="error-state" role="alert">
      <AlertCircle size={24} />
      <div>
        <h3>Something needs your attention</h3>
        <p>{message}</p>
      </div>
      {onRetry && (
        <Button variant="secondary" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}
export function Skeleton({ height = 100, className = "" }) {
  return (
    <div
      className={`skeleton ${className}`}
      style={{ height }}
      aria-label="Loading"
    />
  );
}
export function PageSkeleton() {
  return (
    <div className="page">
      <Skeleton height={74} />
      <div className="metric-grid">
        {Array.from({ length: 8 }, (_, index) => (
          <Skeleton height={125} key={index} />
        ))}
      </div>
      <Skeleton height={320} />
    </div>
  );
}
export function Section({
  id,
  title,
  icon: Icon,
  count,
  children,
  open = true,
  onToggle,
  action,
}) {
  return (
    <details
      className="detail-section"
      id={id}
      open={open}
      onToggle={(event) => onToggle?.(event.currentTarget.open)}
    >
      <summary>
        <span className="section-icon">{Icon && <Icon size={18} />}</span>
        <h2>{title}</h2>
        {count !== undefined && <span className="count-badge">{count}</span>}
        <ChevronDown className="section-chevron" size={18} />
      </summary>
      <div className="section-body">
        {action && <div className="section-action">{action}</div>}
        {children}
      </div>
    </details>
  );
}
export function SupportBadge({ item }) {
  if (
    item.source_type === "manual" ||
    item.grounding_status === "user_provided"
  )
    return (
      <span
        className="support human"
        title="Human-provided record, not an extracted source claim"
      >
        {item.manually_edited ? "User edited" : "User provided"}
      </span>
    );
  const review = item.grounding_status !== "verified";
  return (
    <span
      className={`support ${review ? "review" : ""}`}
      title="Support score is a heuristic, not a calibrated probability. Review the source quote."
    >
      {review ? <AlertCircle size={12} /> : <ShieldCheck size={12} />}
      {review
        ? "Needs review"
        : `${Math.round((item.confidence || 0) * 100)}% support`}
      {item.manually_edited && " · edited"}
    </span>
  );
}

export function Modal({ title, description, children, onClose, wide = false }) {
  const container = useRef(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  useEffect(() => {
    const previous = document.activeElement;
    const oldOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const focusable = () =>
      [
        ...(container.current?.querySelectorAll(
          'button, input, textarea, select, a[href], [tabindex="0"]',
        ) || []),
      ].filter((el) => !el.disabled);
    focusable()[0]?.focus();
    const keyHandler = (event) => {
      if (event.key === "Escape") closeRef.current();
      if (event.key === "Tab") {
        const nodes = focusable();
        const first = nodes[0];
        const last = nodes[nodes.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last?.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first?.focus();
        }
      }
    };
    document.addEventListener("keydown", keyHandler);
    return () => {
      document.body.style.overflow = oldOverflow;
      document.removeEventListener("keydown", keyHandler);
      previous?.focus?.();
    };
  }, []);
  return (
    <div
      className="modal-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        className={`modal ${wide ? "wide" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
        ref={container}
      >
        <div className="modal-header">
          <div>
            <h2 id="modal-title">{title}</h2>
            {description && <p>{description}</p>}
          </div>
          <button
            className="icon-btn"
            aria-label="Close dialog"
            onClick={onClose}
          >
            <X size={20} />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
export function ConfirmDialog({
  title,
  message,
  onConfirm,
  onClose,
  busy = false,
}) {
  return (
    <Modal title={title} onClose={onClose}>
      <p className="confirm-message">{message}</p>
      <div className="modal-actions">
        <Button variant="secondary" onClick={onClose} disabled={busy}>
          Cancel
        </Button>
        <Button variant="danger" busy={busy} onClick={onConfirm}>
          Delete
        </Button>
      </div>
    </Modal>
  );
}
