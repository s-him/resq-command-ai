import { labelize } from "./format.js";

/**
 * Builds a single activity timeline from REAL backend records.
 *
 * The backend's action_history table only logs operator decisions, so two
 * other event types are derived from record timestamps that the API returns:
 *   - incident_reported        <- incident.created_at
 *   - recommendation_generated <- recommendation.created_at
 * Every event carries a `source` so the UI can label it honestly.
 */
export const EVENT_META = {
  incident_reported: { icon: "alert", tone: "blue", label: "Incident reported" },
  recommendation_generated: { icon: "cpu", tone: "cyan", label: "Recommendation generated" },
  recommendation_approved: { icon: "checkCircle", tone: "teal", label: "Recommendation approved" },
  recommendation_rejected: { icon: "xCircle", tone: "slate", label: "Recommendation rejected" },
  incident_status_changed: { icon: "activity", tone: "amber", label: "Incident status changed" },
  incident_operator_note: { icon: "info", tone: "blue", label: "Operator update" },
};

export const EVENT_SOURCE_LABELS = {
  record: "Record timestamp",
  action_log: "Logged operator action",
  incident_timeline: "Incident operational log",
};

export function buildActivityEvents({ incidents = [], recommendations = [], actions = [], incidentUpdates = [] }) {
  const events = [];

  for (const incident of incidents) {
    events.push({
      key: `inc-${incident.id}`,
      type: "incident_reported",
      source: "record",
      timestamp: incident.created_at,
      incidentId: incident.id,
      recommendationId: null,
      description: `${labelize(incident.hazard_type)} at ${incident.location}. Severity assessed as ${incident.severity.level} (${incident.severity.score}/${incident.severity.max_score}).`,
    });
  }

  for (const rec of recommendations) {
    events.push({
      key: `rec-${rec.id}`,
      type: "recommendation_generated",
      source: "record",
      timestamp: rec.created_at,
      incidentId: rec.incident_id,
      recommendationId: rec.id,
      description: rec.summary,
    });
  }

  for (const action of actions) {
    events.push({
      key: `act-${action.id}`,
      type: action.decision === "approved" ? "recommendation_approved" : "recommendation_rejected",
      source: "action_log",
      timestamp: action.created_at,
      incidentId: action.incident_id,
      recommendationId: action.recommendation_id,
      action: action.action,
      decision: action.decision,
      note: action.note,
      description: String(action.note || "").startsWith("system-auto:")
        ? "Approved automatically by the AUTO simulation policy (no human review). Any assignment is virtual."
        : `Operator decision recorded as "${action.decision}". Approval alone reserves no stock and dispatches nothing.`,
    });
  }

  for (const update of incidentUpdates) {
    const isStatusChange = update.event_type === "status_changed";
    const previous = update.previous_status ? labelize(update.previous_status) : "";
    const next = update.new_status ? labelize(update.new_status) : "";
    events.push({
      key: `incident-update-${update.id}`,
      type: isStatusChange ? "incident_status_changed" : "incident_operator_note",
      source: "incident_timeline",
      timestamp: update.created_at,
      incidentId: update.incident_id,
      recommendationId: null,
      note: update.note,
      description: isStatusChange
        ? `Status changed from ${previous} to ${next}.`
        : update.note,
    });
  }

  return events.sort((a, b) => {
    const diff = new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime();
    return diff !== 0 ? diff : b.key.localeCompare(a.key);
  });
}

