"""Pydantic contracts for public feed alerts and operator review."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator\n\nfrom app.schemas import Incident


class AlertSource(str, Enum):
    GDACS = "gdacs"
    USGS = "usgs"


class AlertReviewStatus(str, Enum):
    NEW = "new"
    REVIEWED = "reviewed"
    DISMISSED = "dismissed"


class AlertReviewDecision(str, Enum):
    REVIEWED = "reviewed"
    DISMISSED = "dismissed"


class AlertSyncRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sources: list[AlertSource] = Field(
        default_factory=lambda: [AlertSource.GDACS, AlertSource.USGS],
        min_length=1,
        max_length=2,
        description="One or both configured public sources.",
    )

    @field_validator("sources")
    @classmethod
    def sources_must_be_unique(cls, value: list[AlertSource]) -> list[AlertSource]:
        if len(value) != len(set(value)):
            raise ValueError("sources must not contain duplicates")
        return value


class AlertSyncSourceResult(BaseModel):
    source: AlertSource
    status: str
    fetched_count: int
    created_count: int
    updated_count: int
    error_message: str | None = None
    started_at: datetime
    finished_at: datetime


class AlertSyncResponse(BaseModel):
    status: str
    sources: list[AlertSyncSourceResult]
    fetched_count: int
    created_count: int
    updated_count: int
    disclaimer: str


class AlertSyncRunSummary(BaseModel):
    status: str
    fetched_count: int
    created_count: int
    updated_count: int
    error_message: str | None = None
    started_at: datetime
    finished_at: datetime


class AlertSourceStatus(BaseModel):
    source: AlertSource
    name: str
    hazard_types: list[str]
    feed_url: str
    update_interval: str
    last_sync: AlertSyncRunSummary | None = None


class ExternalAlert(BaseModel):
    id: int
    source: AlertSource
    source_event_id: str
    event_type: str
    hazard_type: str
    title: str
    description: str | None = None
    location: str | None = None
    country: str | None = None
    alert_level: str | None = None
    alert_score: float | None = None
    severity_value: float | None = None
    severity_unit: str | None = None
    severity_text: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    depth_km: float | None = None
    event_at: datetime | None = None
    source_updated_at: datetime | None = None
    source_url: str | None = None
    first_seen_at: datetime
    last_seen_at: datetime
    review_status: AlertReviewStatus
    reviewed_at: datetime | None = None
    review_note: str | None = None
    linked_incident_id: int | None = None
    linked_at: datetime | None = None


class AlertPromotionResponse(BaseModel):
    alert: ExternalAlert
    incident: Incident
    message: str
    disclaimer: str


class AlertListResponse(BaseModel):
    count: int
    total_count: int
    limit: int
    offset: int
    alerts: list[ExternalAlert]
    disclaimer: str


class AlertReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    status: AlertReviewDecision
    note: str | None = Field(default=None, max_length=500)

    @field_validator("note")
    @classmethod
    def blank_note_becomes_none(cls, value: str | None) -> str | None:
        return value or None
