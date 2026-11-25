import { expectArray, expectObject, request } from "./apiClient.js";

/** GET /api/alerts with optional filters and pagination. */
export async function listAlerts({
  source = "all",
  hazardType = "all",
  alertLevel = "all",
  reviewStatus = "all",
  limit = 100,
  offset = 0,
} = {}) {
  const query = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (source !== "all") query.set("source", source);
  if (hazardType !== "all") query.set("hazard_type", hazardType);
  if (alertLevel !== "all") query.set("alert_level", alertLevel);
  if (reviewStatus !== "all") query.set("review_status", reviewStatus);

  return expectObject(
    await request(`/api/alerts?${query.toString()}`),
    "external alerts",
    ["count", "total_count", "alerts", "disclaimer"]
  );
}

/** GET /api/alerts/sources */
export async function listAlertSources() {
  return expectArray(await request("/api/alerts/sources"), "alert sources");
}

/** POST /api/alerts/sync */
export async function syncAlertFeeds(sources = ["gdacs", "usgs"]) {
  return expectObject(
    await request("/api/alerts/sync", {
      method: "POST",
      body: { sources },
    }),
    "sync alert feeds",
    ["status", "sources", "fetched_count", "created_count", "updated_count"]
  );
}

/** POST /api/alerts/{id}/review */
export async function reviewAlert(alertId, status, note = "") {
  return expectObject(
    await request(`/api/alerts/${alertId}/review`, {
      method: "POST",
      body: { status, note: note.trim() || null },
    }),
    "review external alert",
    ["id", "review_status", "reviewed_at"]
  );
}

/** POST /api/alerts/{id}/assessments */
export async function runAlertAssessment(alertId) {
  return expectObject(
    await request(`/api/alerts/${alertId}/assessments`, { method: "POST" }),
    "run alert assessment",
    ["id", "alert_id", "review_priority", "agents", "disclaimer"]
  );
}

/** GET /api/alerts/{id}/assessments */
export async function listAlertAssessments(alertId, limit = 20) {
  return expectObject(
    await request(`/api/alerts/${alertId}/assessments?limit=${limit}`),
    "alert assessment history",
    ["alert_id", "count", "assessments"]
  );
}
