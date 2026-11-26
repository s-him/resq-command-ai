"""
Rule-based resource recommendations (prototype).

IMPORTANT: These are simple demonstration rules for a college mini-project.
They are NOT real emergency dispatch guidance. In MANUAL mode, recommendations
wait for operator approval. In AUTO mode, configured policy may create a
simulated assignment, but physical stock is never reduced and no real dispatch occurs.

HOW MATCHING WORKS
------------------
1. Map each `help_needed` item on the incident to a resource type:
   - medical                      -> ambulance
   - rescue, evacuation, firefighting -> rescue_team
   - shelter                      -> shelter
   - food, water                  -> supply
   - other                        -> other

2. Group help needs that share the same resource type (so e.g. ["food", "water"]
   maps to "supply" once, and we never double-count the same resource).

3. Estimate a simple desired quantity from `people_affected`:
   - shelter / supply: 1 unit per person (minimum 1)
   - ambulance / rescue_team / other: 1 unit per 25 people, rounded up (minimum 1)

4. Look only at resources whose `availability_status` is "available" AND whose
   `quantity_available` is greater than 0. Largest available stock is picked first.
   We NEVER recommend more units than a resource currently has available.

5. If no available resource of a needed type exists, record it clearly in
   `unavailable_needs` so the human operator sees the gap.
"""

import math

from app.geo import haversine_km
from app.schemas import (
    AvailabilityStatus,
    HelpType,
    Incident,
    InsufficientNeed,
    RecommendedResourceItem,
    Resource,
    ResourceType,
    UnavailableNeed,
)

DISCLAIMER = (
    "Unvalidated prototype suggestion for an academic demonstration. "
    "Not real emergency guidance. Physical resource quantities are NOT changed. "
    "MANUAL mode requires operator approval; AUTO mode can create virtual "
    "assignments only under the stored operator settings."
)

# Simple mapping from incident help needs to registered resource types.
HELP_TO_RESOURCE_TYPE: dict[HelpType, ResourceType] = {
    HelpType.MEDICAL: ResourceType.AMBULANCE,
    HelpType.RESCUE: ResourceType.RESCUE_TEAM,
    HelpType.EVACUATION: ResourceType.RESCUE_TEAM,
    HelpType.FIREFIGHTING: ResourceType.RESCUE_TEAM,
    HelpType.SHELTER: ResourceType.SHELTER,
    HelpType.FOOD: ResourceType.SUPPLY,
    HelpType.WATER: ResourceType.SUPPLY,
    HelpType.OTHER: ResourceType.OTHER,
}

# Resource types where 1 unit roughly serves 1 person (e.g. shelter bed or supply kit).
PER_PERSON_RESOURCE_TYPES = {ResourceType.SHELTER, ResourceType.SUPPLY}
PEOPLE_PER_TEAM_UNIT = 25


def desired_quantity_for(resource_type: ResourceType, people_affected: int) -> int:
    """Simple demonstration estimate of how many units to suggest."""
    if resource_type in PER_PERSON_RESOURCE_TYPES:
        return max(1, people_affected)
    return max(1, math.ceil(people_affected / PEOPLE_PER_TEAM_UNIT))


def group_needs_by_resource_type(
    help_needed: list[HelpType],
) -> dict[ResourceType, list[HelpType]]:
    """Group an incident's help_needed list by the matching ResourceType."""
    grouped: dict[ResourceType, list[HelpType]] = {}
    for help_item in help_needed:
        resource_type = HELP_TO_RESOURCE_TYPE[help_item]
        grouped.setdefault(resource_type, []).append(help_item)
    return grouped


def build_recommendation(
    incident: Incident,
    resources: list[Resource],
) -> tuple[list[RecommendedResourceItem], list[UnavailableNeed], list[InsufficientNeed], str]:
    """Match an incident's help_needed list against available resources."""
    # Safety filter: only resources that are "available" and have positive quantity.
    def simulation_remaining(resource: Resource) -> int:
        if resource.simulation_remaining_quantity is not None:
            return resource.simulation_remaining_quantity
        return resource.quantity_available

    eligible = [
        resource
        for resource in resources
        if resource.availability_status == AvailabilityStatus.AVAILABLE
        and simulation_remaining(resource) > 0
    ]

    grouped_needs = group_needs_by_resource_type(incident.help_needed)
    items: list[RecommendedResourceItem] = []
    unavailable_needs: list[UnavailableNeed] = []
    insufficient_needs: list[InsufficientNeed] = []

    for resource_type, matching_help in grouped_needs.items():
        help_label = ", ".join(item.value for item in matching_help)
        candidates = [r for r in eligible if r.resource_type == resource_type]
        has_incident_coordinates = (
            incident.latitude is not None and incident.longitude is not None
        )

        def candidate_distance(resource: Resource) -> float | None:
            if not has_incident_coordinates:
                return None
            if resource.latitude is None or resource.longitude is None:
                return None
            return haversine_km(
                incident.latitude,
                incident.longitude,
                resource.latitude,
                resource.longitude,
            )

        # When the incident has coordinates, geocoded resources are ranked by
        # straight-line proximity first. Ungeocoded resources remain as fallbacks.
        # Without incident coordinates, retain the previous stock-first behavior.
        if has_incident_coordinates:
            candidates.sort(
                key=lambda resource: (
                    candidate_distance(resource) is None,
                    candidate_distance(resource)
                    if candidate_distance(resource) is not None
                    else math.inf,
                    -simulation_remaining(resource),
                    resource.id,
                )
            )
        else:
            candidates.sort(key=lambda resource: (-resource.quantity_available, resource.id))

        if not candidates:
            unavailable_needs.append(
                UnavailableNeed(
                    help_needed=matching_help,
                    resource_type=resource_type,
                    message=(
                        f"No available '{resource_type.value}' resource with positive quantity "
                        f"was found for needed help: {help_label}."
                    ),
                )
            )
            continue

        desired = desired_quantity_for(resource_type, incident.people_affected)
        remaining = desired

        for resource in candidates:
            if remaining <= 0:
                break

            simulation_available = simulation_remaining(resource)
            suggested = min(remaining, simulation_available)
            remaining -= suggested

            if suggested == simulation_available and remaining > 0:
                qty_note = (
                    f"Suggested all {suggested} simulation-unreserved unit(s) "
                    f"(estimated need: {desired} for {incident.people_affected} people affected)."
                )
            else:
                qty_note = (
                    f"Suggested {suggested} of {simulation_available} simulation-unreserved unit(s) "
                    f"(estimated need: {desired} for {incident.people_affected} people affected)."
                )

            distance_km = candidate_distance(resource)
            distance_note = (
                f" Straight-line distance from incident: {distance_km:.2f} km."
                if distance_km is not None
                else " Distance unavailable; this resource is ranked using available stock."
            )

            items.append(
                RecommendedResourceItem(
                    resource_id=resource.id,
                    resource_name=resource.name,
                    resource_type=resource.resource_type,
                    resource_location=resource.location,
                    recommended_quantity=suggested,
                    available_quantity=simulation_available,
                    for_help_needed=matching_help,
                    explanation=f"Matched '{resource_type.value}' for {help_label}. {qty_note}{distance_note}",
                    distance_km=round(distance_km, 2) if distance_km is not None else None,
                    distance_basis=(
                        "haversine_straight_line" if distance_km is not None else "not_available"
                    ),
                )
            )

        if remaining > 0:
            matched_total = desired - remaining
            insufficient_needs.append(
                InsufficientNeed(
                    help_needed=matching_help,
                    resource_type=resource_type,
                    estimated_needed=desired,
                    available_matched=matched_total,
                    shortfall=remaining,
                    message=(
                        f"Insufficient '{resource_type.value}' stock for {help_label}: "
                        f"only {matched_total} of {desired} estimated unit(s) available "
                        f"(shortfall: {remaining})."
                    ),
                )
            )

    summary = (
        f"Recommended {len(items)} resource(s) for incident #{incident.id}; "
        f"{len(unavailable_needs)} unavailable, {len(insufficient_needs)} insufficient."
    )
    return items, unavailable_needs, insufficient_needs, summary

