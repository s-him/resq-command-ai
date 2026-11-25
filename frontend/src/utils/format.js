/**
 * Display-only formatting helpers.
 * These never change values that are sent back to the API.
 */

const dateTimeFormatter = new Intl.DateTimeFormat(undefined, {
  day: "2-digit",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

const dateFormatter = new Intl.DateTimeFormat(undefined, {
  weekday: "long",
  day: "2-digit",
  month: "long",
  year: "numeric",
});

const timeFormatter = new Intl.DateTimeFormat(undefined, {
  hour: "2-digit",
  minute: "2-digit",
});

const numberFormatter = new Intl.NumberFormat();

function toDate(value) {
  if (!value) return null;
  const date = value instanceof Date ? value : new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function formatDateTime(value) {
  const date = toDate(value);
  return date ? dateTimeFormatter.format(date) : "—";
}

export function formatDateHeading(value) {
  const date = toDate(value);
  return date ? dateFormatter.format(date) : "Unknown date";
}

export function formatTime(value) {
  const date = toDate(value);
  return date ? timeFormatter.format(date) : "—";
}

/** Local calendar-day key used to group timeline events. */
export function dateKey(value) {
  const date = toDate(value);
  if (!date) return "unknown";
  return `${date.getFullYear()}-${date.getMonth() + 1}-${date.getDate()}`;
}

export function formatRelative(value, now = new Date()) {
  const date = toDate(value);
  if (!date) return "—";
  const seconds = Math.round((now.getTime() - date.getTime()) / 1000);
  if (seconds < 0) return formatDateTime(date);
  if (seconds < 45) return "just now";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  const days = Math.round(hours / 24);
  if (days < 7) return `${days} d ago`;
  return formatDateTime(date);
}

export function formatNumber(value) {
  return typeof value === "number" && Number.isFinite(value) ? numberFormatter.format(value) : "—";
}

/** "building_collapse" -> "Building collapse" */
export function labelize(value) {
  if (!value) return "";
  const text = String(value).replace(/_/g, " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export const incidentCode = (id) => `INC-${String(id).padStart(4, "0")}`;
export const recommendationCode = (id) => `REC-${String(id).padStart(4, "0")}`;
export const resourceCode = (id) => `RES-${String(id).padStart(4, "0")}`;

/** Value for an <input type="datetime-local"> in the user's local time zone. */
export function toLocalInputValue(date = new Date()) {
  const offsetMs = date.getTimezoneOffset() * 60000;
  return new Date(date.getTime() - offsetMs).toISOString().slice(0, 16);
}

/**
 * The backend's priority explanation repeats the row data in its first sentence
 * ("#1: severity score 70 (High), ... reported <time>.") and then gives the reason.
 * For compact table cells we show only the reason; the full text stays in a tooltip.
 */
export function priorityReason(explanation) {
  if (!explanation) return "";
  const index = explanation.indexOf(". ");
  return index >= 0 ? explanation.slice(index + 2) : explanation;
}

export function pluralize(count, singular, plural = `${singular}s`) {
  return `${formatNumber(count)} ${count === 1 ? singular : plural}`;
}

