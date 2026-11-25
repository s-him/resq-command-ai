import { expectArray, expectObject, request } from "./apiClient.js";

const INCIDENT_KEYS = ["id", "hazard_type", "severity", "status"];

/** GET /api/incidents -> Incident[] (every status, oldest first) */
export async function listIncidents() {
  return expectArray(await request("/api/incidents"), "/api/incidents");
}

/** GET /api/incidents/priority -> { ranking_rules, disclaimer, count, incidents: PrioritizedIncident[] } */
export async function getPriorityQueue() {
  return expectObject(await request("/api/incidents/priority"), "/api/incidents/priority", [
    "ranking_rules",
    "count",
    "incidents",
  ]);
}

/** GET /api/incidents/{id} -> Incident (404 if missing) */
export async function getIncident(incidentId) {
  return expectObject(await request(`/api/incidents/${incidentId}`), "incident", INCIDENT_KEYS);
}

/**
 * POST /api/incidents
 * body: { hazard_type, description, location, reported_at, people_affected,
 *         help_needed[], latitude?, longitude? }
 */
export async function createIncident(payload) {
  return expectObject(
    await request("/api/incidents", { method: "POST", body: payload }),
    "create incident",
    INCIDENT_KEYS
  );
}

/** GET /api/incidents/{id}/history -> { incident_id, recommendations[], action_history[] } */
export async function getIncidentHistory(incidentId) {
  return expectObject(await request(`/api/incidents/${incidentId}/history`), "incident history", [
    "recommendations",
    "action_history",
  ]);
}




/** PATCH /api/incidents/{id}/status -> updated Incident */
export async function updateIncidentStatus(incidentId, status, note = "") {
  return expectObject(
    await request(`/api/incidents/${incidentId}/status`, {
      method: "PATCH",
      body: { status, note: note.trim() || null },
    }),
    "update incident status",
    INCIDENT_KEYS
  );
}

/** POST /api/incidents/{id}/updates -> IncidentUpdateEntry */
export async function addIncidentUpdate(incidentId, note) {
  return expectObject(
    await request(`/api/incidents/${incidentId}/updates`, {
      method: "POST",
      body: { note },
    }),
    "add incident update",
    ["id", "incident_id", "event_type", "note", "created_at"]
  );
}

/** GET /api/incidents/{id}/updates -> IncidentUpdateList */
export async function getIncidentUpdates(incidentId) {
  return expectObject(
    await request(`/api/incidents/${incidentId}/updates`),
    "incident operational history",
    ["incident_id", "count", "active_simulation_count", "updates"]
  );
}


/** POST /api/incidents/{id}/agent-runs -> one persisted advisory agent trace. */
export async function runIncidentAgentPipeline(incidentId) {
  return expectObject(
    await request(`/api/incidents/${incidentId}/agent-runs`, { method: "POST" }),
    "incident agent run",
    ["id", "incident_id", "inputs_summary", "agents", "summary", "engine_version", "duration_ms", "generated_at", "disclaimer"]
  );
}

/** GET /api/incidents/{id}/agent-trace -> recent immutable agent run snapshots. */
export async function getIncidentAgentTrace(incidentId) {
  return expectObject(
    await request(`/api/incidents/${incidentId}/agent-trace`),
    "incident agent trace",
    ["incident_id", "count", "traces", "disclaimer"]
  );
}
