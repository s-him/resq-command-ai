import { expectObject, request } from "./apiClient.js";

/** GET /api/activity -> { count, total_count, entries[] } (newest first) */
export async function listActivity({ limit = 500 } = {}) {
  return expectObject(await request(`/api/activity?limit=${limit}`), "activity log", [
    "count",
    "total_count",
    "entries",
  ]);
}
