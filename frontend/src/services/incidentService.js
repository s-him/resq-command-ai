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

