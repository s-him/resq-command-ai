import { expectObject, request } from "./apiClient.js";

const RECOMMENDATION_KEYS = ["id", "incident_id", "status", "items", "unavailable_needs"];

/** POST /api/incidents/{id}/recommendation -> Recommendation (status "pending") */
export async function generateRecommendation(incidentId) {
  return expectObject(
    await request(`/api/incidents/${incidentId}/recommendation`, { method: "POST" }),
    "generate recommendation",
    RECOMMENDATION_KEYS
  );
}

/** GET /api/recommendations/{id} -> Recommendation */
export async function getRecommendation(recommendationId) {
  return expectObject(
    await request(`/api/recommendations/${recommendationId}`),
    "recommendation",
    RECOMMENDATION_KEYS
  );
}

/**
 * POST /api/recommendations/{id}/decision
 * body: { decision: "approved" | "rejected", note?: string (max 300) }
 * -> { recommendation, history_entry, message }
 */
export async function submitDecision(recommendationId, decision, note) {
  const body = { decision };
  const trimmed = note ? note.trim() : "";
  if (trimmed) body.note = trimmed;
  return expectObject(
    await request(`/api/recommendations/${recommendationId}/decision`, { method: "POST", body }),
    "operator decision",
    ["recommendation", "history_entry", "message"]
  );
}

