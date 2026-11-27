# Test report

> ACADEMIC PROTOTYPE | DEMO DATA IS SIMULATED | AUTO DISPATCH IS VIRTUAL | NOT FOR REAL EMERGENCIES

**Run date:** 27 November 2026
**Environment:** Fedora Linux, Python 3.14.8, Node 22.23.5, FastAPI 0.165.0, pytest 9.2.0, Vite 6.4.6
**Code under test:** commit `86e7299` plus the changes that add this report
**Settings:** automatic feed sync off, LLM off

## Summary

| Check | Result |
|---|---|
| Backend tests (`pytest`) | **282 passed, 0 failed**, 1 existing Starlette/httpx deprecation warning |
| Frontend production build (`npm run build`) | Passed |
| Upgrade of a database created by the previous code | Passed: records kept, history copied into the action log, foreign-key check clean |
| Browser walkthrough (headless Chromium) | Passed for the steps below |

These are local verification results; hosted pull-request CI is a separate check. Feed background loops are disabled inside the isolated pytest fixture, while the production default remains enabled. The no-environment-variable configuration defaults are checked by the final-polish contract tests. Rerun on the machine used for the demonstration:

```bash
cd backend && pytest -q
cd ../frontend && npm ci && npm run build
```

## Results by synopsis test area (section 12)

| Test area | Acceptance condition | Evidence (test files and test counts) | Result |
|---|---|---|---|
| Functional | Incident, inventory, recommendation approval, response-plan reservation and lifecycle actions | test_incidents 29, test_resources 21, test_resource_management 6, test_decisions 13, test_incident_lifecycle 7, test_response_plans 5 | Pass |
| Agent logic | Documented severity/vulnerability scoring and priority rules | test_severity 46, test_prioritization 11, test_area_priority 5, test_agent_pipeline 5, test_assessment_agents 12 | Pass |
| Resource matching | Separate demonstration ratios; never recommend above available stock | test_recommendations 10, test_response_plans 5, test_dispatch 8 | Pass |
| Integration | Five-agent flow, demo scenarios, feed outages and optional LLM path | test_synopsis_requirements 27, test_demo_api 8, test_alerts_api 9, test_llm_smoke_test 5 | Pass (backend) |
| API | Expected status codes and bodies, including stale-approval HTTP 409 | FastAPI test client; test_postman_export 2 | Pass (backend) |
| Usability review | Record issues and improve confusing steps | `USABILITY_REVIEW.md` | **Not yet performed** |

Per-file counts at this revision: test_agent_pipeline 5; test_agent_trace_api 3;
test_alert_promotion 6; test_alert_sources 5; test_alerts_api 9; test_area_priority 5;
test_assessment_agents 12; test_assessments_api 4; test_database 12; test_decisions 13;
test_demo_api 8; test_dispatch 8; test_event_hub 5; test_final_polish_contract 2;
test_geo 8; test_health 2; test_incident_lifecycle 7; test_incidents 29;
test_llm_client 6; test_llm_smoke_test 5; test_postman_export 2; test_prioritization 11;
test_recommendations 10; test_resource_management 6; test_resources 21;
test_response_plans 5; test_severity 46; test_synopsis_requirements 27.
Total: **282 tests**.

## Sample scenarios

| Scenario | How it is tested | Result |
|---|---|---|
| Flood, cyclone, earthquake demos | `test_demo_scenario_creates_labeled_records_and_is_idempotent` (all three) | Pass |
| Adequate stock | `test_recommends_only_needed_quantity_when_plenty_available` | Pass |
| Insufficient stock | `test_never_recommends_more_than_available_and_groups_shared_types` | Pass |
| Unavailable stock | `test_ignores_unavailable_limited_and_zero_quantity_resources` | Pass |
| Severity level boundaries | `test_level_thresholds` | Pass |

## Final-polish feature coverage

- Feed outage tests check one warning per provider failure streak, offline status, retry backoff, and recovery. Saved alerts remain available while a provider is offline.
- Recommendation tests check current stock, simulated reservations, stale approvals returning 409 without changing pending state, rejection without stock, and competing approvals.
- Vulnerability tests cover the six allowed values, empty defaults, duplicate/unknown-value rejection, explicit-over-keyword precedence and the unchanged 5-point maximum. Migration 015 is additive.
- Demo tests confirm scenario inventory sizes, visible shortfalls and preservation of active virtual assignments on repeat runs.
- LLM smoke tests cover disabled/keyless no-write skips, agent modes/rationales, rules fallback and safe error output.
- Final-polish contract tests cover no-environment-variable defaults, SafetyBanner removal and retained safety disclaimers.

## Postman API collection

Import docs/postman_collection.json into Postman. It is generated from the current
FastAPI OpenAPI document by backend/scripts/export_postman.py, includes request
examples from backend/examples/, and defines a baseUrl collection variable
(default http://127.0.0.1:8000). Regenerate it after API schema changes by running
python scripts/export_postman.py from the backend directory.

The generated collection currently contains 53 requests across the OpenAPI operations. The exporter needs the project's existing backend environment, but does not need
the API server to be running or any environment variables to be set.

## Browser walkthrough

Scripted with the flood demo data. It was run by an AI coding assistant, **not** by a
human tester, and does not replace the usability review.

- The dashboard, incident list and detail, resources, recommendations, dispatch,
  alert and history pages and the incident form opened, with no page errors captured.
- A recommendation was approved through the confirmation dialog.
- A response plan and a status change (made through the API) appeared in Activity History.
- The AUTO option was disabled on the Dispatch page.

Not covered: submitting the incident form in the browser, adding or editing resources in
the browser, mobile layout, live GDACS/USGS feeds, a real LLM provider, and `run.bat`.
Map background tiles could not load on the test machine's restricted network.

## Defects fixed in this round

| Defect | Fix |
|---|---|
| Activity History omitted status changes and other actions | New action log and history page |
| AUTO approvals were described as operator decisions with nothing reserved | Corrected text and actor |
| Recency points never aged | Open incidents are re-scored when read |
| "No hospitals nearby" earned vulnerability points | Clearly ruled-out mentions are ignored |
| Dispatch settings panel was never shown | Added to the Dispatch page |
| A report too short after whitespace cleanup caused an unhandled error (found while testing the new code) | Returns a 422 field message |

## Manual verification checklist for the PR reviewer

The automated suite covers the backend contracts. The following browser/client checks
should also be completed against a running local build before presenting the project:

1. Stale stock: create two recommendations that each require the same limited pool,
   approve the first, then approve the second. Expect HTTP 409 naming the resource and
   remaining quantity; the second recommendation must remain pending.
2. Vulnerable groups: create the same incident once without a selection and once
   with a confirmed vulnerable group. Compare the vulnerable-population factor; it must
   award at most 5 points and the explicit selection must override conflicting keywords.
3. Postman: import docs/postman_collection.json, set the collection baseUrl variable,
   and open the included incident/resource/decision example requests.
4. Offline feeds: start with no internet access. Expect one short warning per provider
   outage streak, an offline status from GET /api/alerts/sources and the indicator on
   both Alerts and Dashboard. Repeated retries should not add warning spam; reconnecting
   should clear the provider status.

These manual UI/client checks were not represented as completed by the pytest/build runs.

## Known limitations

- No login or roles.
- Negation handling covers only a few clear phrasings. Other wording that rules a group
  out still scores points.
- Approving a recommendation rechecks and earmarks available capacity without
  changing physical quantities. A simulated response plan turns the earmark into an
  active virtual reservation. Stale approvals return 409 and remain pending.
- A recommendation remains a snapshot. Approval rechecks current stock; if a gap is
  found, regenerate it after checking inventory. Older pending recommendations for
  the same incident stay in the list.
- Severity weights and allocation ratios are not validated; no accuracy is claimed.
- Provider outage status is held in process memory; saved alert data remains in SQLite.
- During a provider outage, fresh feed data is delayed by the capped retry backoff.
