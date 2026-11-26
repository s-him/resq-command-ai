# Autonomous Multi-Agent Disaster Relief & Emergency Dispatch Engine (ResQ Command)

> **ACADEMIC PROTOTYPE | SIMULATED / REPORTED DATA ONLY | HUMAN REVIEW REQUIRED | NOT FOR REAL EMERGENCY DISPATCH**
>
> - This is a **college mini-project demonstration**, not a real emergency response service.
> - It imports read-only public alerts from **GDACS** (multi-hazard) and **USGS** (earthquakes). It does **not** connect to emergency services or live dispatch systems.
> - It does **not** predict disasters.
> - Severity scores and resource matches are **unvalidated rule-based prototype estimates**.
> - A **human operator** must review and approve or reject every recommendation. Approving a recommendation records an audit decision in SQLite and **never dispatches or deducts actual resources**.

---

## Project Overview & Repository Structure

This repository contains a full-stack academic decision-support prototype:

- **`backend/`** — Python **FastAPI** REST API + **SQLite** database (`sqlite3`) with explainable rule-based severity scoring, multi-factor open-incident prioritisation, a resource inventory register, resource recommendation matching, human operator decision logging, GDACS/USGS alert ingestion with deduplication and human review, a five-specialist explainable assessment pipeline, proximity-aware resource matching, a combined incident/resource map, an Alert Intelligence operator page, and a human-gated response-plan simulation ledger, versioned database migrations (`001`–`012`), and a `pytest` test suite.
- **`frontend/`** — **React 19** + **Vite 6** + **Leaflet** operational intelligence dashboard (**ResQ Command**) connected to the FastAPI backend.

```text
.
├── backend/
│   ├── app/
│   │   ├── alert_sources.py           # GDACS + USGS feed parsing and normalization
│   │   ├── alert_repository.py        # External-alert persistence, deduplication and review
│   │   ├── alert_service.py           # Feed synchronization orchestration
│   │   ├── alert_schemas.py           # External-alert API contracts
│   │   ├── geo.py                     # Haversine straight-line distance helper
│   │   ├── response_plan_schemas.py   # Human-gated simulation plan contracts
│   │   ├── response_plan_repository.py # Simulation reservations and audit log
│   │   ├── alert_promotion_service.py  # Atomic reviewed-alert to incident promotion
│   │   ├── agents/                    # Evidence, hazard, recency, location and review agents
│   │   ├── assessment_orchestrator.py # Runs agents and combines their findings
│   │   ├── assessment_repository.py   # Persists immutable assessment snapshots
│   │   ├── assessment_schemas.py      # Assessment API contracts
│   │   ├── main.py                  # FastAPI entry point, lifespan DB init, and CORS config
│   │   ├── config.py                # Project-relative SQLite path (RELIEF_DATABASE_PATH override)
│   │   ├── database.py              # SQLite connection helper (PRAGMA foreign_keys = ON)
│   │   ├── migrations.py            # Versioned SQLite migrations (001-013)
│   │   ├── schemas.py               # Pydantic request/response schemas and validation rules
│   │   ├── severity.py              # Explainable 0–100 rule-based severity scoring
│   │   ├── prioritization.py        # Open-incident priority ranking & tie-breaker explanations
│   │   ├── recommendations.py       # Rule-based resource matching & shortfall reporting
│   │   ├── incident_repository.py   # Parameterized SQLite queries for incidents
│   │   ├── incident_lifecycle_repository.py # Status transitions and operator timeline
│   │   ├── resource_repository.py   # Parameterized SQLite queries for resources
│   │   ├── recommendation_repository.py # Transactional queries for recommendations & action_history
│   │   ├── errors.py                # Structured 422 validation error formatter
│   │   └── routers/                 # /health, /api/alerts, /api/incidents, /api/resources, /api/recommendations, /api/response-plans
│   ├── data/                        # relief.db is created here automatically on first startup
│   ├── examples/                    # Sample JSON request payloads for curl/PowerShell demos
│   ├── tests/                       # Backend pytest suite (current count reported by CI) (each uses a temporary SQLite DB)
│   ├── requirements.txt             # Python dependencies
│   └── README.md                    # Detailed backend API & database schema reference
├── frontend/
│   ├── src/
│   │   ├── config.js                # Central API_BASE_URL configuration (VITE_API_BASE_URL)
│   │   ├── services/                # Central fetch() client and domain API service modules
│   │   ├── context/                 # Shared backend state (DataContext) and operation toasts
│   │   ├── components/              # Layout shell, common UI primitives, map, and forms
│   │   └── pages/                   # Dashboard, Alerts, Incidents, IncidentDetails, Resources, Recommendations, Dispatch Simulation, ActivityHistory
│   ├── .env.example                 # Safe local environment template
│   ├── package.json                 # Frontend packages and scripts
│   ├── package-lock.json            # Lockfile for reproducible npm installs
│   └── README.md                    # Frontend architecture reference
├── .gitignore
└── README.md                        # This file
```

---

## Prerequisites (Fresh Windows 10 / 11 Machine)

1. **Python 3.10 or newer** (tested with Python 3.10–3.14)
   - Verify in PowerShell: `python --version`
   - Note: SQLite support is built into Python's standard library (`sqlite3`), so no separate database server installation is required.
2. **Node.js 18.18+ or 20+ LTS** (includes `npm`)
   - Verify in PowerShell: `node --version` and `npm --version`
3. **Git** (to clone the repository)

---

## Quick Start (Fresh Clone on Windows PowerShell)

Open **Windows PowerShell** and clone the repository:

```powershell
git clone https://github.com/s-him/resq-command-ai.git
cd resq-command-ai
```

You will run the **backend** in **Terminal 1** and the **frontend** in **Terminal 2**.

---

### Terminal 1 — Backend Setup & Startup (`backend/`)

From the repository root folder:

```powershell
# 1. Enter the backend directory
cd backend

# 2. Create an isolated Python virtual environment (.venv)
python -m venv .venv

# 3. Activate the virtual environment
.\.venv\Scripts\Activate.ps1

# 4. Install Python dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt

# 5. Start the FastAPI server on http://127.0.0.1:8000
uvicorn app.main:app --reload
```

> **Note on SQLite initialization:** You do **not** need an existing database file. On first startup, `uvicorn` automatically creates `backend/data/relief.db` and runs versioned migrations `001`–`013` to initialize all tables (`incidents`, `resources`, `recommendations`, `recommendation_items`, `action_history`, `external_alerts`, `alert_sync_runs`, `alert_assessments`, `response_plans`, `response_plan_items`, `response_plan_actions`, `resource_change_history`, `incident_updates`, `incident_agent_runs`, and `schema_migrations`). Migration 008 adds an optional link from a reviewed external alert to the incident created from it. Migration 009 adds resource registration and inventory-change audit history. Migration 010 adds timestamped incident status and operator-note history. Migration 011 adds immutable incident-agent traces. Migration 012 adds optional event time, hazard measurement and provider alert fields; existing incidents are rescored once under the new rules version without losing their original incident data.

---

### Terminal 2 — Frontend Setup & Startup (`frontend/`)

Open a **second** Windows PowerShell window at the repository root folder:

```powershell
# 1. Enter the frontend directory
cd frontend

# 2. Install frontend dependencies reproducibly from package-lock.json
npm ci
# (Or run `npm install` if you prefer)

# 3. Optional: create a local .env file from .env.example
Copy-Item .env.example .env

# 4. Start the Vite development server on http://localhost:5173
npm run dev
```

---

## Local Application & API URLs

Once both terminals are running:

| Service | Local URL | Purpose |
|---|---|---|
| **Frontend Dashboard (ResQ Command)** | http://localhost:5173 | Main operator interface |
| **Backend Root** | http://127.0.0.1:8000 | API landing JSON |
| **Backend Health Check** | http://127.0.0.1:8000/health | Reports API & SQLite connection status |
| **Interactive API Docs (Swagger UI)** | http://127.0.0.1:8000/docs | Test all backend endpoints in the browser |

---

## Configuration & Environment Variables

### Frontend (`frontend/.env`)
The frontend reads `VITE_API_BASE_URL` from `frontend/src/config.js` and defaults to `http://127.0.0.1:8000` if no `.env` file is present. To customize it:

```powershell
cd frontend
Copy-Item .env.example .env
```

Contents of `frontend/.env.example`:
```ini
VITE_API_BASE_URL=http://127.0.0.1:8000
```

### Backend SQLite Path (`backend/app/config.py`)
By default, SQLite stores data at the project-relative path `backend/data/relief.db`.
If you want to run the backend against a temporary or custom database file without touching `backend/data/relief.db`, set `RELIEF_DATABASE_PATH` in PowerShell before starting `uvicorn`:

```powershell
$env:RELIEF_DATABASE_PATH = "C:\Temp\demo_relief.db"
uvicorn app.main:app --reload
```

---

## Running Automated Checks & Production Build

### Backend Test Suite (`pytest`)
Each test in `backend/tests/` uses its own temporary SQLite file (`tmp_path`), so running `pytest` never modifies `backend/data/relief.db`:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pytest
```

### Frontend Production Build (`vite build`)
To verify that all React components and assets bundle cleanly for production:

```powershell
cd frontend
npm run build
```

---

## Troubleshooting Common Setup Issues on Windows

1. **PowerShell blocks `.\.venv\Scripts\Activate.ps1` ("running scripts is disabled on this system"):**
   Run this command once in PowerShell to allow local scripts for your Windows user account, then re-run `.\.venv\Scripts\Activate.ps1`:
   ```powershell
   Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
   ```
2. **`ModuleNotFoundError: No module named 'app'` when starting `uvicorn`:**
   Make sure your terminal working directory is `backend/` (not the repository root) before running `uvicorn app.main:app --reload`, and confirm your virtual environment (`(.venv)`) is activated.
3. **Frontend topbar shows `Connection unavailable`:**
   - Check that **Terminal 1** (`uvicorn app.main:app --reload`) is running on `http://127.0.0.1:8000`.
   - Open http://127.0.0.1:8000/health in your browser to confirm it returns `{"status":"ok", ...}`.
   - If you changed the backend port, update `VITE_API_BASE_URL` in `frontend/.env` and restart `npm run dev`.
4. **CORS errors in the browser console:**
   `backend/app/main.py` allows `http://localhost:5173` and `http://127.0.0.1:5173`. Always open the frontend on port `5173` (Vite's configured port in `frontend/vite.config.js`). If port `5173` is already in use by another process, stop the old process so Vite binds to `5173`.

---

## Multi-agent alert assessment (Stage 2)

An imported external alert can be assessed with five explainable specialist agents:

1. Evidence quality — checks which source fields are present. This is completeness, not truth or probability.
2. Hazard signal — preserves GDACS alert levels and USGS magnitude/depth without inventing a universal severity scale.
3. Event recency — checks the age and plausibility of the provider event timestamp.
4. Location evidence — records coordinate availability and explicitly leaves population exposure unknown.
5. Review coordinator — assigns a conservative human-review queue label and explains why.

Run an assessment:

```bash
curl -X POST http://127.0.0.1:8000/api/alerts/1/assessments
```

Read assessment history:

```bash
curl http://127.0.0.1:8000/api/alerts/1/assessments
```

Read one saved assessment:

```bash
curl http://127.0.0.1:8000/api/alerts/assessments/1
```

Each run is saved as an immutable snapshot in `alert_assessments`. The pipeline is currently deterministic and rule-based; it is not a trained ML model or an LLM. It does not create an incident, estimate exposed population, contact responders, allocate supplies, or dispatch teams.

Migration `005` adds the assessment snapshot table and links it to the original external alert.

---

## Geographic resource planning (Stage 3)

Resources can now be registered with optional latitude/longitude. The dashboard map plots both incident coordinates and registered resource depot coordinates. The recommendation engine uses Haversine straight-line distance to rank geocoded resources nearest-first when an incident also has coordinates; resources without coordinates remain as fallbacks. If the incident has no coordinates, the earlier stock-first behavior is retained.

The nearby resource API is `GET /api/resources/nearby?latitude=28.6139&longitude=77.2090&radius_km=25`. It returns only available resources with positive stock, registered coordinates, and a calculated straight-line distance within the requested radius.

Straight-line distance is not road distance or travel time. This stage does not model flood/cyclone/earthquake impact boundaries, estimate affected population, or claim that registered resources are verified or deployable.

---

## Human-gated response plan simulation (Stage 4)

A response plan can be created only from a resource recommendation that has already been approved by an operator. Creating a plan leaves it pending. A second operator must explicitly approve the plan to move it to `simulated`, which records reservations in a separate simulation ledger. A plan can also be rejected. Completing a simulated plan releases its simulation-only reservations.

**This is not a real dispatch system.** No emergency service is contacted, no team or vehicle is sent, and the physical `resources.quantity_available` value is never modified. The operator approval is a prototype UI gate; there is no authentication or role-based authorization yet. Active simulated reservations reduce the `simulation_remaining_quantity` shown in inventory and used by subsequent recommendations, preventing overlapping simulations from overbooking the same registered stock.

| Method | URL | Purpose |
|---|---|---|
| POST | `/api/incidents/{incident_id}/response-plans` | Create a pending plan from an approved recommendation |
| GET | `/api/response-plans` | List plans (optional `?status=pending`) |
| GET | `/api/response-plans/{plan_id}` | Inspect a plan and its audit history |
| POST | `/api/response-plans/{plan_id}/decision` | Approve into simulation or reject |
| POST | `/api/response-plans/{plan_id}/complete` | Complete a simulation and release reservations |

The frontend exposes this workflow under **Dispatch Simulation**. Each plan records its resource assignments, operator decisions, notes and timestamps.

---

## Alert Intelligence dashboard (Stage 5)

The React application now includes an Alert Intelligence page at `#/alerts`. Operators can synchronize the configured GDACS and USGS feeds, filter imported alerts by provider/hazard/provider alert level/review state, open the original source report, record a reviewed/dismissed decision, and run the five-specialist assessment pipeline on an individual alert.

The alert list and source status refresh from the local API every 60 seconds. Separately, the backend runs scheduled provider sync loops by default: GDACS every 6 minutes and USGS every 1 minute. Operators can also trigger an immediate sync with **Sync Public Feeds**. The browser refresh only reloads local API data; it does not itself fetch provider feeds.

All alert records remain external, unverified reports until an operator independently verifies them. The assessment panel shows per-agent findings and limitations; it does not create an incident or authorize a response.

---

## Promote a reviewed alert into an incident (Stage 6)

An external alert can be promoted only after its review state is `reviewed`. The operator must supply or confirm the incident hazard type, description, location, event/report time, affected-person estimate, and at least one help type. Coordinates are copied only when the provider supplied them; they remain optional.

```bash
curl -X POST http://127.0.0.1:8000/api/alerts/1/promote \
  -H 'Content-Type: application/json' \
  -d '{"hazard_type":"flood","description":"Operator-verified flooding in homes near Example District.","location":"Example District","reported_at":"2026-11-25T10:00:00Z","people_affected":75,"help_needed":["evacuation","medical"],"latitude":26.9,"longitude":75.8}'
```

The operation is atomic: it creates one open incident using the existing prototype severity calculation and stores `linked_incident_id` / `linked_at` on the source alert. A duplicate promotion returns HTTP 409. The new incident immediately appears in `/api/incidents` and `/api/incidents/priority`, and can use the existing resource recommendation flow.

The feed does not supply an affected-person count or help-needed list. Those values are never inferred from magnitude, provider alert level, or coordinates. This remains an operator-assisted prototype, not an automatic emergency decision.

---

## Automatic public-feed synchronization (Stage 7)

The FastAPI backend now starts independent background sync loops when the application starts: GDACS every 6 minutes by default, and USGS every 1 minute by default. Provider requests run in worker threads so they do not block normal API handling. Each provider has its own loop and failure log. The Alert Intelligence page continues refreshing the local API list every 60 seconds; the provider sync itself happens in the backend.

Automatic sync is enabled by default. Disable it for offline work:

```bash
RESQ_ALERT_AUTO_SYNC_ENABLED=false ./run.sh
```

Change the intervals (seconds) without editing code:

```bash
RESQ_GDACS_SYNC_INTERVAL_SECONDS=600 RESQ_USGS_SYNC_INTERVAL_SECONDS=120 ./run.sh
```

The intervals must be at least 30 seconds; invalid or smaller values fall back to defaults. Manual **Sync Public Feeds** remains available. Manual and scheduled syncs for the same provider are serialized so they cannot race one another.

---

## Resource readiness and inventory control (Stage 8)

Resources can now be edited from the inventory page. Operators can update resource type, name, physical quantity, depot location, availability status, and optional coordinates. Each registration/update is recorded in `resource_change_history`, including before/after values, timestamp, and optional operator note.

The API supports `PATCH /api/resources/{resource_id}` and `GET /api/resources/{resource_id}/history`. Inventory changes are transactional. Physical quantity cannot be reduced below active simulation reservations, and a resource cannot be marked unavailable while a simulated plan still reserves units. Complete the simulation to release the reservation first.

The resource page displays physical stock separately from simulation-reserved and simulation-remaining quantities. This is still a prototype inventory register; it is not connected to a live hospital/agency inventory system.

---

## Incident operations lifecycle (Stage 9)

Incidents now support an explicit operator lifecycle: `open → resolved → closed`, with `resolved → open` available for reopening when new information arrives. Closed incidents are final in this prototype. Status changes and operator-entered field notes are stored chronologically in `incident_updates`.

| Method | URL | Purpose |
|---|---|---|
| PATCH | `/api/incidents/{incident_id}/status` | Apply an allowed status transition and optional note |
| POST | `/api/incidents/{incident_id}/updates` | Add an operator note to the incident timeline |
| GET | `/api/incidents/{incident_id}/updates` | Read status changes and operational notes; includes active simulation count |

An incident cannot be closed while any response plan remains `simulated`. Complete those simulation plans first; the server enforces this rule transactionally. Open incidents remain in the priority queue; resolved and closed incidents do not.

Operator notes are prototype audit entries and do not prove that responders attended or conditions changed. There is no operator authentication or role-based access control yet.


---

## Incident-level AI-assisted agent pipeline (Phase 1)

A separate incident-level workflow now runs five named agents in order: **DetectionAgent**, **SeverityAgent**, **PrioritizationAgent**, **DispatchAgent**, and **CoordinatorAgent**. This does not replace the existing GDACS/USGS external-alert assessment endpoint; that original five-specialist feed assessment remains deterministic.

- **DetectionAgent** reviews an existing manual or promoted incident and, when available, its linked normalized GDACS/USGS alert. It can draft a hazard classification, description, location, and people-at-risk estimate for an operator to verify. It never creates or edits an incident.
- **SeverityAgent** reports the existing deterministic severity score and factor breakdown. An enabled LLM may add explanatory text, but cannot change the numeric score or level.
- **PrioritizationAgent** uses the deterministic score → people affected → report time → ID ordering. An LLM may add wording but cannot reorder the queue.
- **DispatchAgent** calls the existing nearest/available-resource matcher and reports its assignments and shortfalls. LLM text cannot change resource IDs or quantities.
- **CoordinatorAgent** summarizes the validated outputs and states the next human review step.

Each run stores input summary, agent output, mode (llm or rules), rationale, confidence field, per-agent duration, total duration, and generation time. The confidence field is a prototype display value, not a calibrated probability.

### Incident agent API

| Method | URL | Purpose |
|---|---|---|
| POST | /api/incidents/{incident_id}/agent-runs | Run all five agents and persist an immutable trace |
| GET | /api/incidents/{incident_id}/agent-trace | Read the most recent trace snapshots |

Open an incident in the UI and select **Run Agent Pipeline**. Its **Agent Activity** section displays each agent's mode, timing, rationale, and structured output.

### Optional LLM configuration

LLM use is **disabled by default**. The app works offline and uses deterministic rules when disabled. If enabled, it sends JSON-mode requests to an OpenAI-compatible /chat/completions endpoint using the existing httpx dependency; no additional SDK is required.

Copy .env.example as a reference, then set the values in the environment used to launch FastAPI. The example file is not loaded automatically by the application.

| Variable | Default | Purpose |
|---|---|---|
| LLM_ENABLED | false | Explicit opt-in to LLM calls |
| LLM_BASE_URL | https://api.openai.com/v1 | OpenAI-compatible API base URL |
| LLM_API_KEY | empty | Optional provider key; never commit a real key |
| LLM_MODEL | gpt-4o-mini | Provider model identifier |
| LLM_TIMEOUT_SECONDS | 8 | Per-request timeout |

Linux/macOS example:

~~~bash
export LLM_ENABLED=true
export LLM_BASE_URL="https://api.openai.com/v1"
export LLM_API_KEY="YOUR_KEY_IN_YOUR_SHELL_ONLY"
export LLM_MODEL="gpt-4o-mini"
export LLM_TIMEOUT_SECONDS=8
cd backend
uvicorn app.main:app --reload
~~~

Windows PowerShell example:

~~~powershell
$env:LLM_ENABLED = "true"
$env:LLM_BASE_URL = "https://api.openai.com/v1"
$env:LLM_API_KEY = "YOUR_KEY_IN_YOUR_SHELL_ONLY"
$env:LLM_MODEL = "gpt-4o-mini"
$env:LLM_TIMEOUT_SECONDS = "8"
cd backend
uvicorn app.main:app --reload
~~~

Every provider response must be JSON and pass its agent's Pydantic schema. A disabled provider, missing configuration, HTTP error, timeout, malformed JSON, or schema-validation failure triggers deterministic fallback. Do not put real API keys in source control, screenshots, logs, or issue reports.

**Safety boundary:** LLM output is a suggestion only. It cannot create/modify incidents, change severity scores or priority order, reserve stock, approve a recommendation, create a response plan, or dispatch resources. Phase 1 remains advisory; automatic simulated dispatch is a separate later phase and must retain explicit safety controls.


---

## Severity rules v2 and affected-area priority (Phase 2)

Severity remains a transparent **0–100 prototype estimate**, not a calibrated probability or official emergency instruction. Rules version `demo-rules-v2` adds four evidence dimensions to the existing people/help factors:

| Factor | Maximum | Rule summary |
|---|---:|---|
| People affected | 35 | Reported people-count bands |
| Immediate help | 20 | No immediate need: 5; one immediate type: 15; multiple: 20 |
| Hazard type | 10 | Small declared-category baseline weight |
| Hazard signal | 15 | Strongest supported provider alert level or hazard measurement |
| Event/report recency | 15 | Under 1 hour: 15; up to 6 hours: 12; up to 24 hours: 9; up to 72 hours: 5; older/missing: 0 |
| Vulnerable population | 5 | Explicit hospital, school, elderly, child, infant or care-setting terms in report text |

Hazard signal bands include GDACS-style `green` / `orange` / `red` alert levels, USGS-style earthquake magnitudes, cyclone category/wind measurements, and flood-water depth with supported units. If both a provider alert level and magnitude are supplied, the strongest supported signal is used once, not added twice. Unsupported units are stored for context and receive no invented points.

Open incidents retain the deterministic order **severity score → people affected → earlier report time → ID**. The new `GET /api/incidents/areas/priority` endpoint groups open incidents by the recorded location string (trimmed and matched case-insensitively), then ranks areas by highest individual incident score, total reported people affected, earliest report, and top incident ID. It does not geocode locations, infer administrative boundaries, or query population data.

Older incidents with a previous or missing rules version are recalculated at startup using the stored incident fields and migration 012 metadata columns. No incident is deleted. The new area view is shown on the main dashboard and can be refreshed with the rest of the dashboard data.


---

## Automatic dispatch simulation (Phase 3)

The operator-controlled setting is stored in SQLite and defaults to **MANUAL**.
In MANUAL mode, recommendations and response plans continue to require the
existing operator decisions. In AUTO mode, open incidents at or above the
configured High/Critical threshold run the five-agent trace, create a resource
recommendation, and create a simulated deployment assignment.

AUTO reservations are created in one `BEGIN IMMEDIATE` transaction. The
transaction re-checks resource availability and active reservations before it
records the recommendation approval, response plan, per-resource deployment
assignment, and audit events. Each deployment records `incident_id`,
`resource_id`, quantity, state and actor (`system-auto`). Resource inventory
reports both reserved and deployed quantities; the physical stock quantity is
not edited. The ledger prevents double-reservation and negative remaining stock.

The emergency pause switch prevents new AUTO assignments and shortfall retries.
Complete and Recall release the virtual reservation and record lifecycle events.
When new resource stock is added or increased, previously recorded shortfalls
are retried in deterministic incident priority order. The retry calculates only
the remaining unfilled quantity after earlier active assignments, rather than
requesting the full original amount again.

API:
- `GET/PATCH /api/dispatch/settings` — read or update mode, pause state and minimum severity.
- `GET /api/dispatch/deployments` — view per-resource assignments and their lifecycle state.
- `GET /api/dispatch/audit` — inspect audit events, including the `system-auto` actor.
- `POST /api/dispatch/incidents/{id}/retry` — explicitly retry a recorded shortfall.
- `POST /api/response-plans/{id}/recall` — recall an active AUTO simulation.
- `POST /api/response-plans/{id}/complete` — complete and release an active simulation.

**Safety boundary:** this is not real-world dispatch. AUTO creates database
assignments and virtual stock reservations only. It does not contact emergency
services, send SMS, move real teams/vehicles, or physically deduct inventory.
The mode switch and emergency pause are operator workflow controls in this
academic prototype, not authenticated security controls.


---

## Real-time dashboard (Phase 4)

The FastAPI backend exposes \`GET /api/events/stream\` as Server-Sent Events.
A thread-safe in-process event hub broadcasts lightweight change notices after
alerts arrive or incidents, recommendations, resources, response plans,
dispatch settings, and agent runs change. The event stream is an invalidation
signal; the frontend reloads canonical records using the existing REST APIs.

The React data context owns one shared \`EventSource\` connection. The browser
reconnects automatically; while SSE is unavailable, a 10-second REST polling
fallback keeps dashboard data current. The top bar shows **LIVE**,
**RECONNECTING**, or **POLLING**.

The dashboard shows:
- A newest-first GDACS/USGS alerts feed with provider severity badges.
- The Leaflet map with severity-coloured incident locations and resource markers.
- Resource availability by rescue teams, ambulances, shelters and supplies,
  separating unreserved available stock from active simulated deployments.
- Active response-plan operations with assigned units, straight-line distance,
  an explicit unavailable ETA, and Complete/Recall actions.
- A lightweight SVG incidents-by-hazard chart.

SSE uses a bounded in-process queue and is suitable for this single-process
academic prototype. It is not a durable event log or a cross-worker broker.
A multi-worker deployment would need shared messaging. If the browser misses
an event, reconnect and REST refresh restore current state.
