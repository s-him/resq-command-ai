import React from "react";
import { STATUS_LABELS } from "../../utils/constants";
import { labelize } from "../../utils/format";
import Icon from "./Icon";

/**
 * Severity badge: always displays text + dot/icon alongside color for accessibility.
 */
export function SeverityBadge({ level, score, maxScore = 100, showScore = false }) {
  const safeLevel = level || "Low";
  return (
    <span className={`sev-badge sev-${safeLevel}`}>
      <span className="sev-dot" aria-hidden="true" />
      <span>{safeLevel}</span>
      {showScore && typeof score === "number" && (
        <span className="sev-score tabular">
          {score}/{maxScore}
        </span>
      )}
    </span>
  );
}

const STATUS_ICONS = {
  open: "activity",
  resolved: "checkCircle",
  closed: "xCircle",
  pending: "clock",
  approved: "checkCircle",
  rejected: "xCircle",
  simulated: "activity",
  completed: "checkCircle",
  new: "alert",
  reviewed: "checkCircle",
  dismissed: "xCircle",
  available: "checkCircle",
  limited: "alert",
  unavailable: "xCircle",
};

export function StatusBadge({ status }) {
  const key = String(status || "").toLowerCase();
  const label = STATUS_LABELS[key] || labelize(key);
  const icon = STATUS_ICONS[key] || "info";
  return (
    <span className={`status-badge status-${key}`}>
      <Icon name={icon} size={13} />
      <span>{label}</span>
    </span>
  );
}

export function CodeBadge({ children, onClick }) {
  if (onClick) {
    return (
      <button type="button" className="code-badge code-badge-btn tabular" onClick={onClick}>
        {children}
      </button>
    );
  }
  return <span className="code-badge tabular">{children}</span>;
}

