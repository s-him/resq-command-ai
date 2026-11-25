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



/**
 * GET /api/resources/nearby -> NearbyResourceList
 * Distances are straight-line Haversine estimates, not road travel times.
 */
export async function findNearbyResources({ latitude, longitude, radiusKm = 25 }) {
  const query = new URLSearchParams({
    latitude: String(latitude),
    longitude: String(longitude),
    radius_km: String(radiusKm),
  });
  return expectObject(
    await request(`/api/resources/nearby?${query.toString()}`),
    "nearby resources",
    ["latitude", "longitude", "radius_km", "resources"]
  );
}



/** PATCH /api/resources/{id} */
export async function updateResource(resourceId, payload) {
  return expectObject(
    await request(`/api/resources/${resourceId}`, {
      method: "PATCH",
      body: payload,
    }),
    "update resource",
    ["id", "resource_type", "quantity_available", "availability_status"]
  );
}

/** GET /api/resources/{id}/history */
export async function getResourceHistory(resourceId) {
  return expectObject(
    await request(`/api/resources/${resourceId}/history`),
    "resource history",
    ["resource_id", "count", "entries"]
  );
}
