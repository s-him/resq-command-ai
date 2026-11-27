# Requirement traceability

Test files are in `backend/tests/`; code paths are relative to the repository root.

| ID | Requirement | Code | Test evidence |
|---|---|---|---|
| FR-1 | Create/view incidents with optional operator-reported vulnerable groups | backend/app/routers/incidents.py, backend/app/schemas.py, migration 015, incident form/details | test_incidents.py, test_database.py |
| FR-2 | Severity from documented rules; explicit vulnerable groups override narrative fallback without changing the 5-point cap | backend/app/severity.py; rules tables in README.md and backend/README.md | test_severity.py, test_incidents.py |
| FR-3 | Order open incidents by priority | `backend/app/prioritization.py` | `test_prioritization.py`, `test_area_priority.py`, live-score tests in `test_synopsis_requirements.py` |
| FR-4 | Revalidate current stock inside a serialized approval transaction; return 409 and retain pending state when stale | backend/app/recommendation_repository.py, backend/app/routers/recommendations.py | test_decisions.py, test_response_plans.py |
| FR-5 | Approve or reject a recommendation | `backend/app/routers/recommendations.py` | `test_decisions.py` |
| FR-6 | Record status changes; show alerts and history | `backend/app/migrations.py` (migration 014), `backend/app/activity_service.py`, `frontend/src/pages/ActivityHistory.jsx` | `test_incident_lifecycle.py`, alert and action-log tests in `test_synopsis_requirements.py` |
| NFR-1 | Understandable in a short demo | `frontend/src/` | **Pending:** classmate review, see `USABILITY_REVIEW.md` |
| NFR-2 | Reject invalid records with a useful message | `backend/app/schemas.py`, `backend/app/errors.py` | validation tests in `test_incidents.py`, `test_resources.py` |
| NFR-3 | Validate input; no stored credentials | Pydantic schemas; LLM key read from the environment | validation tests. **No login exists**, so modification actions are not restricted |
| NFR-4 | Separate agent responsibilities; documented scoring | `backend/app/agents/`, `README.md` | `test_agent_pipeline.py` |
| NFR-5 | Explain ranking and recommendations | priority, severity-factor and recommendation explanations | `test_prioritization.py`, `test_severity.py` |
| NFR-6 | Continue serving saved alerts during provider outages and expose per-provider health | backend/app/alert_service.py, backend/app/main.py, backend/app/routers/alerts.py, Alerts/dashboard panels | test_alerts_api.py, test_alert_sources.py |
| NFR-7 | Export a portable API client collection and safely smoke-test optional LLM agents | backend/scripts/export_postman.py, backend/scripts/llm_smoke_test.py, docs/postman_collection.json | test_postman_export.py, test_llm_smoke_test.py |

## Synopsis agents

| Synopsis agent | Module in `backend/app/agents/` |
|---|---|
| Monitoring | `monitoring_agent.py` (field validation: `schemas.py`; ID: database) |
| Severity Assessment | `severity_agent.py` |
| Area Prioritisation | `prioritization_agent.py`; area ranking in `prioritization.py` |
| Resource Allocation | `resource_allocation_agent.py` |
| Notification and Logging | `notification_agent.py`; log writes by database triggers |

## API paths

All paths in synopsis section 7.1 are available. `POST /api/resources` adds a record;
updates use `PATCH /api/resources/{id}`. `POST /api/actions/{id}/decision` takes the
recommendation ID and is the same operation as `POST /api/recommendations/{id}/decision`.

## Feed resilience and approval safeguards

GDACS and USGS sync remains enabled by default. Each provider has its own failure streak
and retry backoff; the first failure logs one warning, GET /api/alerts/sources exposes
ok/offline state and offline_since, and a successful fetch clears the state. Saved alerts
remain available during an outage and the UI shows a compact offline indicator.

Recommendation approval rechecks all recommended items under BEGIN IMMEDIATE, subtracting
active simulated plans, deployed AUTO assignments and other approved-but-not-yet-simulated
recommendation holds. A shortage returns HTTP 409 and leaves the recommendation pending;
rejection is still permitted without stock.

IncidentCreate accepts an optional vulnerable_groups list containing children, elderly,
hospital, school, pregnant_women and disabled. Migration 015 adds the field with an empty
default for existing incident rows. The explicit selections take precedence over the
description/location keyword fallback and do not change the 5-point factor maximum.

## API additions and state behavior

- GET /api/alerts/sources — per-provider sync state, offline timestamp, failure count and retry delay.
- POST /api/recommendations/{recommendation_id}/decision — HTTP 409 when current stock cannot fully cover approval.
- POST /api/incidents — optional vulnerable_groups list.
- POST /api/demo/simulate — repeatable cyclone, flood and earthquake scenarios.
- GET /api/events/stream — SSE invalidation stream.

## Postman collection

Import docs/postman_collection.json into Postman. It is generated from app.openapi()
by backend/scripts/export_postman.py, includes checked-in request bodies from
backend/examples/, and uses the baseUrl variable. The optional LLM smoke test is
backend/scripts/llm_smoke_test.py.

## Data design differences

Recommendations are stored as a header (`recommendations`) plus one row per resource
(`recommendation_items`). The synopsis "Alerts / Action Log" entity is `action_log`
(`id` = log_id, `created_at` = timestamp). Active alerts are calculated from current
records and are not stored.


## Safety boundary

**Academic prototype. Demo data is simulated. AUTO assignments are virtual dispatch only.
This system is not for real emergencies.** It does not contact emergency services, send
real responders or vehicles, or verify resource availability. The LLM layer is optional
and disabled by default.
