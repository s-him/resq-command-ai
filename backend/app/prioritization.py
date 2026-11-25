"""
Incident prioritisation (prototype).

Puts open incidents in priority order, highest first, and explains each
position. This is a demonstration ordering to help a human operator review
incidents; it is NOT real emergency guidance.

RANKING ORDER
-------------
1. Higher severity score first.          (the main factor, from severity.py)
2. Same score?  More people affected first.
3. Still tied?  Older report (earlier reported_at) first.
4. Still tied?  Lower ID first (it was saved earlier), so the order is always the same.

Why sort in Python instead of SQL "ORDER BY"?
reported_at is stored as text and may use different time zones, for example
"10:30+05:30" (which is 05:00 UTC) and "06:00+00:00" (06:00 UTC). Sorting the
text would put them in the wrong order, so we convert every time to UTC first.
"""

from datetime import datetime, timezone

from app.schemas import Incident, PrioritizedIncident, PriorityInfo

RANKING_RULES = [
    "1. Higher severity score first.",
    "2. If scores are equal: more people affected first.",
    "3. If still equal: older report (earlier reported_at) first.",
    "4. If still equal: lower incident ID (saved earlier) first.",
]

DISCLAIMER = (
    "Prototype ordering based on unvalidated severity estimates, for an academic "
    "demonstration. Not real emergency guidance. A human operator must review it."
)


def reported_at_utc(incident: Incident) -> datetime:
    """reported_at converted to UTC so different time zones compare correctly.

    A time without a time zone is treated as the server's local time.
    """
    return incident.reported_at.astimezone(timezone.utc)


def priority_sort_key(incident: Incident) -> tuple:
    """The values Python sorts by, in order of importance.

    Python sorts small values first, so we use minus signs to put
    HIGHER scores and MORE people first.
    """
    return (
        -incident.severity.score,  # 1. higher score first
        -incident.people_affected,  # 2. more people first
        reported_at_utc(incident),  # 3. older report first
        incident.id,  # 4. lower ID first
    )


def explain_against_next(incident: Incident, next_incident: Incident | None, next_rank: int) -> str:
    """Say which rule put this incident above the one ranked just below it."""
    if next_incident is None:
        return "Lowest priority of the open incidents."

    score, next_score = incident.severity.score, next_incident.severity.score
    if score != next_score:
        return f"Above #{next_rank} because of a higher severity score ({score} vs {next_score})."

    people, next_people = incident.people_affected, next_incident.people_affected
    if people != next_people:
        return (
            f"Above #{next_rank}: same severity score ({score}), "
            f"but more people affected ({people} vs {next_people})."
        )

    if reported_at_utc(incident) != reported_at_utc(next_incident):
        return (
            f"Above #{next_rank}: same severity score ({score}) and people affected ({people}), "
            f"but reported earlier ({incident.reported_at.isoformat()} vs "
            f"{next_incident.reported_at.isoformat()})."
        )

    return (
        f"Above #{next_rank}: same score, people affected and reported time, "
        f"but saved earlier (ID {incident.id} vs {next_incident.id})."
    )


def rank_incidents(incidents: list[Incident]) -> list[PrioritizedIncident]:
    """Sort incidents by priority and attach a rank and explanation to each."""
    ordered = sorted(incidents, key=priority_sort_key)

    ranked = []
    for index, incident in enumerate(ordered):
        rank = index + 1
        next_incident = ordered[index + 1] if index + 1 < len(ordered) else None

        summary = (
            f"#{rank}: severity score {incident.severity.score} ({incident.severity.level.value}), "
            f"{incident.people_affected} people affected, reported {incident.reported_at.isoformat()}."
        )
        comparison = explain_against_next(incident, next_incident, rank + 1)

        ranked.append(
            PrioritizedIncident(
                **incident.model_dump(),
                priority=PriorityInfo(rank=rank, explanation=f"{summary} {comparison}"),
            )
        )
    return ranked

