import { expectObject, request } from "./apiClient.js";

/** Run a fully labeled synthetic scenario through the standard incident workflow. */
export async function runDemoScenario(scenario) {
  return expectObject(
    await request("/api/demo/simulate", {
      method: "POST",
      body: { scenario },
    }),
    "demo simulation",
    [
      "scenario",
      "dispatch_mode",
      "alerts_created",
      "incidents_created",
      "resources_created",
      "incident_ids",
      "agent_runs",
      "dispatched_count",
      "message",
      "disclaimer",
    ]
  );
}
