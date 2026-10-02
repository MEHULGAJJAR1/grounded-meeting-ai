export const STATUSES = [
  "Pending",
  "In Progress",
  "Completed",
  "Blocked",
  "Cancelled",
];
export const PRIORITIES = ["Low", "Medium", "High", "Critical"];
export const FILTERS = [
  "All",
  "Pending",
  "Completed",
  "Overdue",
  "High Priority",
  "Unassigned",
  "My Tasks",
];
export const CHART_COLORS = [
  "#258469",
  "#7d72cf",
  "#efb66a",
  "#ed7e77",
  "#abb8b0",
];

export function dateLabel(value, options = {}) {
  if (!value) return "Not specified";
  const date = /^\d{4}-\d{2}-\d{2}$/.test(value)
    ? new Date(`${value}T12:00:00`)
    : new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("en", {
    day: "numeric",
    month: "short",
    ...options,
  }).format(date);
}
export function localDate(timezone) {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: timezone || "Asia/Kolkata",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
}
export function initials(name) {
  return (name || "U")
    .split(/\s+/)
    .map((word) => word[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
}
export function slug(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-");
}
export function fileSize(bytes) {
  return bytes < 1024 * 1024
    ? `${Math.max(1, Math.round(bytes / 1024))} KB`
    : `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
export function isOverdue(item, today) {
  return (
    item.due_date &&
    item.due_date < today &&
    !["Completed", "Cancelled"].includes(item.status)
  );
}
export function dependencyText(value) {
  return typeof value === "string" ? value : value.text;
}
