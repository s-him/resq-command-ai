"""
Data shapes (schemas) for the API, built with Pydantic.

Pydantic checks every incoming request against these classes. If a field is
missing or has the wrong type/value, FastAPI automatically rejects the request
with a clear error message - our code never sees the bad data.
"""

from datetime import datetime, timedelta, timezone
from typing import Any
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class HazardType(str, Enum):
    """Allowed kinds of hazard. Using a fixed list keeps the data consistent."""

    FLOOD = "flood"
    EARTHQUAKE = "earthquake"
    FIRE = "fire"
    CYCLONE = "cyclone"
    LANDSLIDE = "landslide"
    BUILDING_COLLAPSE = "building_collapse"
    CHEMICAL_SPILL = "chemical_spill"
    OTHER = "other"


class HelpType(str, Enum):
    """Allowed kinds of help a report can ask for."""

    RESCUE = "rescue"
    MEDICAL = "medical"
    EVACUATION = "evacuation"
    SHELTER = "shelter"
    FOOD = "food"
    WATER = "water"
    FIREFIGHTING = "firefighting"
    OTHER = "other"


class IncidentStatus(str, Enum):
    """Lifecycle status of an incident. Only open incidents are priority-ranked."""

    OPEN = "open"
    RESOLVED = "resolved"
    CLOSED = "closed"


class SeverityLevel(str, Enum):
    """Severity levels, from least to most severe."""

    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


class SeverityFactor(BaseModel):
    """One rule that contributed points to the severity score."""

    factor: str  # e.g. "people_affected"
    points: int  # points this factor added
    max_points: int  # the most this factor can ever add
    reason: str  # short human-readable reason


class SeverityAssessment(BaseModel):
    """The calculated severity of an incident (prototype estimate, see severity.py)."""

    score: int
    max_score: int
    level: SeverityLevel
    explanation: str
    factors: list[SeverityFactor]
    rules_version: str
    disclaimer: str


class IncidentCreate(BaseModel):
    """What a client must send to POST /api/incidents."""

    model_config = ConfigDict(
        str_strip_whitespace=True,  # "  flood  " -> "flood"; "   " counts as empty
        extra="forbid",  # reject unknown fields (e.g. a client trying to set "id" or "status")
        json_schema_extra={
            "examples": [
                {
                    "hazard_type": "flood",
                    "description": "Water entering ground-floor homes near the river bank.",
                    "location": "Ward 12, Riverside Road",
                    "reported_at": "2026-11-19T10:30:00+05:30",
                    "people_affected": 40,
                    "help_needed": ["evacuation", "food"],
                }
            ]
        },
    )

    hazard_type: HazardType
    description: str = Field(min_length=10, max_length=1000)
    location: str = Field(min_length=2, max_length=200)
    reported_at: datetime
    people_affected: int = Field(ge=0, le=1_000_000)
    help_needed: list[HelpType] = Field(min_length=1, max_length=len(HelpType))
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)

    @model_validator(mode="after")
    def coordinates_must_be_paired(self) -> "IncidentCreate":
        """If one coordinate is provided, the other must be provided too."""
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Provide both latitude and longitude, or leave both empty")
        return self

    @field_validator("reported_at")
    @classmethod
    def reported_at_not_in_future(cls, value: datetime) -> datetime:
        """A report cannot come from the future (5 minutes allowed for clock differences)."""
        now = datetime.now(value.tzinfo) if value.tzinfo else datetime.now()
        if value > now + timedelta(minutes=5):
            raise ValueError("reported_at cannot be in the future")
        return value

    @field_validator("help_needed")
    @classmethod
    def help_needed_no_duplicates(cls, value: list[HelpType]) -> list[HelpType]:
        """Each type of help should be listed only once."""
        if len(value) != len(set(value)):
            raise ValueError("help_needed must not contain duplicates")
        return value


class Incident(BaseModel):
    """What the API sends back: the saved incident, including server-set fields."""

    id: int
    hazard_type: HazardType
    description: str
    location: str
    reported_at: datetime
    people_affected: int
    help_needed: list[HelpType]
    status: IncidentStatus
    created_at: datetime
    severity: SeverityAssessment
    latitude: float | None = None
    longitude: float | None = None



class IncidentStatusUpdate(BaseModel):
    """Request to move an incident through its operator-managed lifecycle."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    status: IncidentStatus
    note: str | None = Field(default=None, max_length=500)

    @field_validator("note")
    @classmethod
    def blank_note_as_none(cls, value: str | None) -> str | None:
        return value or None


class IncidentOperatorNote(BaseModel):
    """A free-form operational update recorded in the incident timeline."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    note: str = Field(min_length=3, max_length=1000)


class IncidentUpdateEntry(BaseModel):
    id: int
    incident_id: int
    event_type: str
    previous_status: IncidentStatus | None = None
    new_status: IncidentStatus | None = None
    note: str | None = None
    created_at: datetime


class IncidentUpdateList(BaseModel):
    incident_id: int
    count: int
    active_simulation_count: int
    updates: list[IncidentUpdateEntry]
    disclaimer: str


class PriorityInfo(BaseModel):
    """Where an incident sits in the priority list, and why."""

    rank: int  # 1 = highest priority
    explanation: str


class PrioritizedIncident(Incident):
    """An incident plus its position in the priority list."""

    priority: PriorityInfo


class PriorityList(BaseModel):
    """Response of GET /api/incidents/priority."""

    ranking_rules: list[str]
    disclaimer: str
    count: int
    incidents: list[PrioritizedIncident]


class ResourceType(str, Enum):
    """Allowed kinds of relief resource."""

    AMBULANCE = "ambulance"
    RESCUE_TEAM = "rescue_team"
    SHELTER = "shelter"
    SUPPLY = "supply"
    OTHER = "other"


class AvailabilityStatus(str, Enum):
    """Current availability of a registered resource."""

    AVAILABLE = "available"
    LIMITED = "limited"
    UNAVAILABLE = "unavailable"


class ResourceCreate(BaseModel):
    """What a client must send to POST /api/resources."""

    model_config = ConfigDict(
        str_strip_whitespace=True,  # trim surrounding spaces; blank strings count as empty
        extra="forbid",  # reject unknown fields (e.g. a client trying to set "id")
        json_schema_extra={
            "examples": [
                {
                    "resource_type": "ambulance",
                    "name": "City Hospital Ambulance Unit A",
                    "quantity_available": 3,
                    "location": "Central Depot, Ward 4",
                    "availability_status": "available",
                }
            ]
        },
    )

    resource_type: ResourceType
    name: str = Field(min_length=2, max_length=120)
    quantity_available: int = Field(ge=0, le=1_000_000)
    location: str = Field(min_length=2, max_length=200)
    availability_status: AvailabilityStatus
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)

    @model_validator(mode="after")
    def coordinates_must_be_paired(self) -> "ResourceCreate":
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Provide both latitude and longitude, or leave both empty")
        return self


class Resource(BaseModel):
    """What the API sends back: the saved resource, including server-set fields."""

    id: int
    resource_type: ResourceType
    name: str
    quantity_available: int
    location: str
    availability_status: AvailabilityStatus
    created_at: datetime
    latitude: float | None = None
    longitude: float | None = None
    simulation_reserved_quantity: int = 0
    simulation_remaining_quantity: int | None = None



class ResourceUpdate(BaseModel):
    """Partial resource maintenance request. Only supplied fields are changed."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    resource_type: ResourceType | None = None
    name: str | None = Field(default=None, min_length=2, max_length=120)
    quantity_available: int | None = Field(default=None, ge=0, le=1_000_000)
    location: str | None = Field(default=None, min_length=2, max_length=200)
    availability_status: AvailabilityStatus | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    note: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_update_fields(self) -> "ResourceUpdate":
        editable_fields = {
            "resource_type",
            "name",
            "quantity_available",
            "location",
            "availability_status",
            "latitude",
            "longitude",
        }
        supplied = editable_fields.intersection(self.model_fields_set)
        if not supplied:
            raise ValueError("Provide at least one resource field to update")
        for field in supplied - {"latitude", "longitude"}:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        coordinates_supplied = {"latitude", "longitude"}.intersection(self.model_fields_set)
        if coordinates_supplied and coordinates_supplied != {"latitude", "longitude"}:
            raise ValueError("Provide both latitude and longitude, or update neither")
        if coordinates_supplied and ((self.latitude is None) != (self.longitude is None)):
            raise ValueError("Provide both coordinates or clear both coordinates")
        return self

    @field_validator("note")
    @classmethod
    def blank_note_as_none(cls, value: str | None) -> str | None:
        return value or None


class ResourceHistoryEntry(BaseModel):
    id: int
    resource_id: int
    action: str
    changes: dict[str, dict[str, Any]]
    note: str | None = None
    created_at: datetime


class ResourceHistory(BaseModel):
    resource_id: int
    count: int
    entries: list[ResourceHistoryEntry]


class NearbyResource(Resource):
    distance_km: float


class NearbyResourceList(BaseModel):
    latitude: float
    longitude: float
    radius_km: float
    count: int
    resources: list[NearbyResource]
    disclaimer: str


class RecommendationStatus(str, Enum):
    """Review status of a generated resource recommendation.

    Every new recommendation starts as "pending" until a human operator reviews it.
    """

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class RecommendedResourceItem(BaseModel):
    """One matching resource suggested for an incident."""

    resource_id: int
    resource_name: str
    resource_type: ResourceType
    resource_location: str
    recommended_quantity: int
    available_quantity: int
    for_help_needed: list[HelpType]
    explanation: str
    distance_km: float | None = None
    distance_basis: str = "not_available"


class UnavailableNeed(BaseModel):
    """A needed resource type that had no available units."""

    help_needed: list[HelpType]
    resource_type: ResourceType
    message: str


class InsufficientNeed(BaseModel):
    """A needed resource type with some available units, but fewer than estimated."""

    help_needed: list[HelpType]
    resource_type: ResourceType
    estimated_needed: int
    available_matched: int
    shortfall: int
    message: str


class Recommendation(BaseModel):
    """Saved resource recommendation returned by the API."""

    id: int
    incident_id: int
    status: RecommendationStatus
    items: list[RecommendedResourceItem]
    unavailable_needs: list[UnavailableNeed]
    insufficient_needs: list[InsufficientNeed] = []
    summary: str
    disclaimer: str
    created_at: datetime
    decision_note: str | None = None
    decided_at: datetime | None = None


class OperatorDecision(str, Enum):
    """Allowed operator decisions for POST /api/recommendations/{id}/decision."""

    APPROVED = "approved"
    REJECTED = "rejected"


class DecisionCreate(BaseModel):
    """Request body for recording an operator decision on a recommendation."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "decision": "approved",
                    "note": "Reviewed by operator; logged for prototype demo.",
                }
            ]
        },
    )

    decision: OperatorDecision
    note: str | None = Field(default=None, max_length=300)

    @field_validator("note")
    @classmethod
    def empty_note_as_none(cls, value: str | None) -> str | None:
        """Treat a blank note as None so we don't store empty strings."""
        return value if value else None


class ActionHistoryEntry(BaseModel):
    """One recorded operator action linked to an incident and recommendation."""

    id: int
    incident_id: int
    recommendation_id: int
    action: str
    decision: OperatorDecision
    note: str | None = None
    created_at: datetime


class DecisionResult(BaseModel):
    """Response returned after recording an operator decision."""

    recommendation: Recommendation
    history_entry: ActionHistoryEntry
    message: str


class IncidentHistory(BaseModel):
    """Recommendations and operator action history for a single incident."""

    incident_id: int
    recommendations: list[Recommendation]
    action_history: list[ActionHistoryEntry]


def utc_now() -> datetime:
    """Current time in UTC (used for created_at)."""
    return datetime.now(timezone.utc)

