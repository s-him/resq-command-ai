import { expectArray, expectObject, request } from "./apiClient.js";

/** GET /api/response-plans -> ResponsePlanList */
export async function listResponsePlans(status = null) {
  const query = status ? `?status=${encodeURIComponent(status)}` : "";
  const result = expectObject(
    await request(`/api/response-plans${query}`),
    "response plans",
    ["count", "plans", "disclaimer"]
  );
  if (!Array.isArray(result.plans)) {
    throw new Error("The response plan API returned an invalid plans list.");
  }
  return result;
}

/** POST /api/incidents/{id}/response-plans */
export async function createResponsePlan(incidentId, recommendationId) {
  return expectObject(
    await request(`/api/incidents/${incidentId}/response-plans`, {
      method: "POST",
      body: { recommendation_id: recommendationId },
    }),
    "create response plan",
    ["id", "incident_id", "recommendation_id", "status"]
  );
}

/** POST /api/response-plans/{id}/decision */
export async function decideResponsePlan(planId, decision, note = "") {
  return expectObject(
    await request(`/api/response-plans/${planId}/decision`, {
      method: "POST",
      body: { decision, note: note.trim() || null },
    }),
    "response plan decision",
    ["plan", "message"]
  );
}

/** POST /api/response-plans/{id}/complete */
export async function completeResponsePlan(planId, note = "") {
  return expectObject(
    await request(`/api/response-plans/${planId}/complete`, {
      method: "POST",
      body: { note: note.trim() || null },
    }),
    "complete response plan",
    ["id", "status"]
  );
}
