"""
Rule-based severity scoring (prototype).

IMPORTANT: This is an UNVALIDATED PROTOTYPE ESTIMATE made for a college
demonstration. The rules below are simple and invented for teaching purposes.
They are NOT real emergency guidance and must not be used to make real
decisions. A human operator always reviews the result.

HOW THE SCORE WORKS (total 0-100 points)
----------------------------------------
Factor 1 - Estimated people affected (0-60 points)
    0 people         ->  0 points
    1-9 people       -> 10 points
    10-49 people     -> 25 points
    50-199 people    -> 40 points
    200-999 people   -> 50 points
    1000+ people     -> 60 points

Factor 2 - Is immediate (life-safety) help needed? (10-40 points)
    "Immediate" help types are: rescue, medical, evacuation, firefighting.
    Only basic needs (shelter, food, water, other) -> 10 points
    One immediate help type                       -> 30 points
    Two or more immediate help types              -> 40 points

Severity level from the total score
    0-24  -> Low
    25-49 -> Medium
    50-74 -> High
    75-100 -> Critical

Example: 60 people affected (40 points) + medical help needed (30 points)
         = 70 points -> High
"""

from app.schemas import HelpType, SeverityAssessment, SeverityFactor, SeverityLevel

# Change this label whenever the rules change, so old scores can be identified.
RULES_VERSION = "demo-rules-v1"

MAX_SCORE = 100

DISCLAIMER = (
    "Unvalidated prototype estimate for an academic demonstration. "
    "Not real emergency guidance. A human operator must review it."
)

# Factor 1: (minimum number of people, points). Checked from the top down.
PEOPLE_BANDS = [
    (1000, 60),
    (200, 50),
    (50, 40),
    (10, 25),
    (1, 10),
    (0, 0),
]
PEOPLE_MAX_POINTS = 60

# Factor 2: which kinds of help count as "immediate" (life-safety).
IMMEDIATE_HELP_TYPES = {
    HelpType.RESCUE,
    HelpType.MEDICAL,
    HelpType.EVACUATION,
    HelpType.FIREFIGHTING,
}
POINTS_NO_IMMEDIATE_HELP = 10
POINTS_ONE_IMMEDIATE_HELP = 30
POINTS_MULTIPLE_IMMEDIATE_HELP = 40
HELP_MAX_POINTS = 40

# Severity levels: (minimum score, level). Checked from the top down.
LEVEL_THRESHOLDS = [
    (75, SeverityLevel.CRITICAL),
    (50, SeverityLevel.HIGH),
    (25, SeverityLevel.MEDIUM),
    (0, SeverityLevel.LOW),
]


def score_people_affected(people_affected: int) -> SeverityFactor:
    """Factor 1: more people affected -> more points."""
    points = 0
    for minimum_people, band_points in PEOPLE_BANDS:
        if people_affected >= minimum_people:
            points = band_points
            break

    noun = "person" if people_affected == 1 else "people"
    return SeverityFactor(
        factor="people_affected",
        points=points,
        max_points=PEOPLE_MAX_POINTS,
        reason=f"{people_affected} {noun} affected",
    )


def score_immediate_help(help_needed: list[HelpType]) -> SeverityFactor:
    """Factor 2: requests for life-safety help -> more points."""
    immediate = [help_type.value for help_type in help_needed if help_type in IMMEDIATE_HELP_TYPES]

    if len(immediate) >= 2:
        points = POINTS_MULTIPLE_IMMEDIATE_HELP
        reason = "multiple types of immediate help needed: " + ", ".join(immediate)
    elif len(immediate) == 1:
        points = POINTS_ONE_IMMEDIATE_HELP
        reason = f"immediate help needed: {immediate[0]}"
    else:
        points = POINTS_NO_IMMEDIATE_HELP
        basic = ", ".join(help_type.value for help_type in help_needed)
        reason = f"no immediate help needed (basic needs only: {basic})"

    return SeverityFactor(
        factor="immediate_help",
        points=points,
        max_points=HELP_MAX_POINTS,
        reason=reason,
    )


def level_for_score(score: int) -> SeverityLevel:
    """Turn a 0-100 score into Low / Medium / High / Critical."""
    for minimum_score, level in LEVEL_THRESHOLDS:
        if score >= minimum_score:
            return level
    return SeverityLevel.LOW


def calculate_severity(people_affected: int, help_needed: list[HelpType]) -> SeverityAssessment:
    """Calculate the severity score, level and explanation for one incident."""
    factors = [
        score_people_affected(people_affected),
        score_immediate_help(help_needed),
    ]
    score = sum(factor.points for factor in factors)
    level = level_for_score(score)

    # e.g. "Score 70/100 (High): 60 people affected (+40); immediate help needed: medical (+30)"
    parts = [f"{factor.reason} (+{factor.points})" for factor in factors]
    explanation = f"Score {score}/{MAX_SCORE} ({level.value}): " + "; ".join(parts)

    return SeverityAssessment(
        score=score,
        max_score=MAX_SCORE,
        level=level,
        explanation=explanation,
        factors=factors,
        rules_version=RULES_VERSION,
        disclaimer=DISCLAIMER,
    )

