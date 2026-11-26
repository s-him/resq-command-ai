import { expectObject, request } from "./apiClient.js";

export async function getDispatchSettings() {
  return expectObject(
    await request("/api/dispatch/settings"),
    "dispatch settings",
    ["mode", "paused", "minimum_severity", "updated_at", "updated_by"]
  );
}

export async function updateDispatchSettings(payload) {
  return expectObject(
    await request("/api/dispatch/settings", { method: "PATCH", body: payload }),
    "update dispatch settings",
    ["mode", "paused", "minimum_severity", "updated_at", "updated_by"]
  );
}

export async function recallResponsePlan(planId, note = "") {
  return expectObject(
    await request("/api/response-plans/" + planId + "/recall", {
      method: "POST",
      body: { note: note.trim() || null },
    }),
    "recall response plan",
    ["id", "status", "dispatch_mode"]
  );
}
