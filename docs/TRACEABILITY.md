# Requirement traceability

Test files are in `backend/tests/`; code paths are relative to the repository root.

| ID | Requirement | Code | Test evidence |
|---|---|---|---|
| FR-1 | Create and view incidents | `backend/app/routers/incidents.py`, `frontend/src/pages/Incidents.jsx` | `test_incidents.py` |
| FR-2 | Severity from a documented rule set | `backend/app/severity.py`; rules table in `README.md` | `test_severity.py` |
| FR-3 | Order open incidents by priority | `backend/app/prioritization.py` | `test_prioritization.py`, `test_area_priority.py`, live-score tests in `test_synopsis_requirements.py` |
| FR-4 | Check availability before recommending | `backend/app/recommendations.py` | `test_recommendations.py`, `test_response_plans.py` |
| FR-5 | Approve or reject a recommendation | `backend/app/routers/recommendations.py` | `test_decisions.py` |
| FR-6 | Record status changes; show alerts and history | `backend/app/migrations.py` (migration 014), `backend/app/activity_service.py`, `frontend/src/pages/ActivityHistory.jsx` | `test_incident_lifecycle.py`, alert and action-log tests in `test_synopsis_requirements.py` |
| NFR-1 | Understandable in a short demo | `frontend/src/` | **Pending:** classmate review, see `USABILITY_REVIEW.md` |
| NFR-2 | Reject invalid records with a useful message | `backend/app/schemas.py`, `backend/app/errors.py` | validation tests in `test_incidents.py`, `test_resources.py` |
| NFR-3 | Validate input; no stored credentials | Pydantic schemas; LLM key read from the environment | validation tests. **No login exists**, so modification actions are not restricted |
| NFR-4 | Separate agent responsibilities; documented scoring | `backend/app/agents/`, `README.md` | `test_agent_pipeline.py` |
| NFR-5 | Explain ranking and recommendations | priority, severity-factor and recommendation explanations | `test_prioritization.py`, `test_severity.py` |

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

## Data design differences

Recommendations are stored as a header (`recommendations`) plus one row per resource
(`recommendation_items`). The synopsis "Alerts / Action Log" entity is `action_log`
(`id` = log_id, `created_at` = timestamp). Active alerts are calculated from current
records and are not stored.
