import { expectObject, request } from "./apiClient.js";

/** GET /health -> { status, app, version, database, mode } */
export async function getHealth() {
  return expectObject(await request("/health"), "/health", ["status"]);
}

