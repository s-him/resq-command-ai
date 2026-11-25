import { expectArray, expectObject, request } from "./apiClient.js";

/** GET /api/resources -> Resource[] */
export async function listResources() {
  return expectArray(await request("/api/resources"), "/api/resources");
}

/**
 * POST /api/resources
 * body: { resource_type, name, quantity_available, location, availability_status }
 */
export async function createResource(payload) {
  return expectObject(
    await request("/api/resources", { method: "POST", body: payload }),
    "create resource",
    ["id", "resource_type", "quantity_available"]
  );
}

