
/**
 * Exact enum values accepted by the FastAPI backend.
 * The UI shows friendlier labels, but API payloads use these values.
 */

export const HAZARD_TYPES = [
  "flood",
  "earthquake",
  "fire",
  "cyclone",
  "landslide",
  "building_collapse",
  "chemical_spill",
  "other",
];

export const HELP_TYPES = [
  "rescue",
  "medical",
  "evacuation",
  "shelter",
  "food",
  "water",
  "firefighting",
  "other",
];

export const RESOURCE_TYPES = [
  "ambulance",
  "rescue_team",
  "shelter",
  "supply",
  "other",
];

export const AVAILABILITY_STATUSES = [
  "available",
  "limited",
  "unavailable",
];

export const INCIDENT_STATUSES = [
  "open",
  "resolved",
  "closed",
];

export const RECOMMENDATION_STATUSES = [
  "pending",
  "approved",
  "rejected",
];

/** Severity levels returned by the backend, most severe first. */
export const SEVERITY_LEVELS = [
  "Critical",
  "High",
  "Medium",
  "Low",
];

export const SEVERITY_COLORS = {
  Critical: "var(--severity-critical-text)",
  High: "var(--severity-high-text)",
  Medium: "var(--severity-medium-text)",
  Low: "var(--severity-low-text)",
};

export const HAZARD_ICONS = {
  flood: "waves",
  earthquake: "activity",
  fire: "flame",
  cyclone: "wind",
  landslide: "mountain",
  building_collapse: "building",
  chemical_spill: "flask",
  other: "alert",
};

export const RESOURCE_ICONS = {
  ambulance: "ambulance",
  rescue_team: "lifebuoy",
  shelter: "home",
  supply: "package",
  other: "helpCircle",
};

export const HELP_ICONS = {
  rescue: "lifebuoy",
  medical: "ambulance",
  evacuation: "arrowRight",
  shelter: "home",
  food: "package",
  water: "droplet",
  firefighting: "flame",
  other: "helpCircle",
};

export const STATUS_LABELS = {
  // Incidents
  open: "Open",
  resolved: "Resolved",
  closed: "Closed",

  // Recommendations
  pending: "Pending review",
  approved: "Approved",
  rejected: "Rejected",
  simulated: "Simulated (reserved)",
  completed: "Completed",
  new: "New alert",
  reviewed: "Reviewed",
  dismissed: "Dismissed",

  // Resource availability
  available: "Available",
  limited: "Limited",
  unavailable: "Unavailable",
};

export const SAFETY_NOTICE =
  "EXTERNAL ALERTS ARE UNVERIFIED | LIVE UPDATES ARE INFORMATIONAL | DEMO RECORDS ARE SIMULATED | AUTO ASSIGNMENTS ARE VIRTUAL | NO REAL RESPONDER OR STOCK MOVEMENT | NOT FOR REAL EMERGENCY USE";

export const HUMAN_REVIEW_WARNING =
  "Operator review is required. Approving a recommendation does not reserve stock; stock is reserved (virtually) only when its response plan is approved. Nothing here is a real dispatch instruction.";


export const VULNERABLE_GROUPS = [
  "children",
  "elderly",
  "hospital",
  "school",
  "pregnant_women",
  "disabled",
];
