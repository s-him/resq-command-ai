# Test report

**Run date:** 26 November 2026
**Environment:** Linux, Python 3.13.18, Node 22.23.5, FastAPI 0.165.0, pytest 9.2.0
**Code under test:** commit `86e7299` plus the changes that add this report
**Settings:** automatic feed sync off, LLM off

## Summary

| Check | Result |
|---|---|
| Backend tests (`pytest`) | **260 passed, 0 failed**, 1 library deprecation warning |
| Frontend production build (`npm run build`) | Passed |
| Upgrade of a database created by the previous code | Passed: records kept, history copied into the action log, foreign-key check clean |
| Browser walkthrough (headless Chromium) | Passed for the steps below |

CI uses Python 3.12 and had not run on these changes when this report was written.
Rerun the tests on the machine used for the demonstration:

```bash
cd backend && pytest -q
cd ../frontend && npm ci && npm run build
```

## Results by synopsis test area (section 12)

| Test area | Acceptance condition | Evidence (test files and test counts) | Result |
|---|---|---|---|
| Functional | Each API/UI action gives the correct result | `test_incidents` 27, `test_resources` 21, `test_resource_management` 6, `test_decisions` 10, `test_incident_lifecycle` 7, `test_response_plans` 5 | Pass (API); UI only as listed below |
| Agent logic | Outputs follow the documented rules | `test_severity` 44, `test_prioritization` 11, `test_area_priority` 5, `test_agent_pipeline` 5, `test_assessment_agents` 12 | Pass |
| Resource matching | Never recommend more units than available | `test_recommendations` 9, including the cases below | Pass |
| Integration | A report goes through all agent stages and is recorded | `test_synopsis_requirements` (new incident runs five agents; full manual workflow is logged), `test_demo_api` 5 | Pass (backend) |
| API | Expected status codes and bodies | FastAPI test client across the API test files, valid and invalid requests | Pass |
| Usability review | Record issues and improve confusing steps | `USABILITY_REVIEW.md` | **Not yet performed** |

The remaining files are `test_alert_promotion` 6, `test_alert_sources` 5, `test_alerts_api` 7,
`test_assessments_api` 4, `test_agent_trace_api` 3, `test_database` 12, `test_dispatch` 8,
`test_event_hub` 5, `test_geo` 8, `test_health` 2 and `test_llm_client` 6.
`test_synopsis_requirements` has 27 test cases.

## Sample scenarios

| Scenario | How it is tested | Result |
|---|---|---|
| Flood, cyclone, earthquake demos | `test_demo_scenario_creates_labeled_records_and_is_idempotent` (all three) | Pass |
| Adequate stock | `test_recommends_only_needed_quantity_when_plenty_available` | Pass |
| Insufficient stock | `test_never_recommends_more_than_available_and_groups_shared_types` | Pass |
| Unavailable stock | `test_ignores_unavailable_limited_and_zero_quantity_resources` | Pass |
| Severity level boundaries | `test_level_thresholds` | Pass |

## Postman API collection

Import docs/postman_collection.json into Postman. It is generated from the current
FastAPI OpenAPI document by backend/scripts/export_postman.py, includes request
examples from backend/examples/, and defines a baseUrl collection variable
(default http://127.0.0.1:8000). Regenerate it after API schema changes by running
python scripts/export_postman.py from the backend directory.

The exporter needs the project's existing backend environment, but does not need
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
- Severity weights are not validated; no accuracy is claimed.
