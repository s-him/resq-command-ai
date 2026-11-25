# Backend – Autonomous Multi-Agent Disaster Relief & Emergency Dispatch Engine

> **Academic prototype for a college mini-project.**
> - Imports read-only public alert data from GDACS (multi-hazard) and USGS (earthquakes), alongside manually entered reports.
> - It is **not** a real emergency system and does **not** connect to emergency services or live dispatch systems.
> - It does **not** predict disasters.
> - A **human operator** must approve or reject every recommendation.

This backend provides a FastAPI API, SQLite persistence, manual incident reporting, prototype severity scoring, resource recommendations, operator decision logging, read-only public alert ingestion, specialist-agent assessment, proximity-aware resource matching, and simulation-only response plans. External alerts are stored separately from incidents until an operator reviews them.

---

## Folder structure

```
backend/
├── app/                    # All application code lives here
│   ├── __init__.py         # Marks "app" as a Python package
│   ├── main.py             # Creates the FastAPI app and registers routers
│   ├── config.py           # App name, version, database path (all settings in one place)
│   ├── database.py         # SQLite connection (PRAGMA foreign_keys = ON) + init_database()
│   ├── migrations.py       # Versioned SQLite migrations (schema_migrations, safe table rebuilds)
│   ├── alert_sources.py    # GDACS/USGS feed fetch and normalization
│   ├── alert_repository.py # External alert persistence, deduplication and review
│   ├── alert_service.py    # Feed synchronization orchestration
│   ├── alert_schemas.py    # External alert API contracts
│   ├── geo.py              # Haversine straight-line distance helper
│   ├── agents/             # Evidence, hazard, recency, location and review specialists
│   ├── assessment_orchestrator.py # Runs the specialists and combines findings
│   ├── assessment_repository.py   # Stores immutable assessment snapshots
│   ├── assessment_schemas.py      # Assessment response contracts
│   ├── response_plan_schemas.py   # Human-gated simulation plan contracts
│   ├── response_plan_repository.py # Simulation reservations and audit history
│   ├── schemas.py          # Pydantic models for incidents and resources
│   ├── severity.py         # Rule-based severity scoring (prototype estimate)
│   ├── prioritization.py   # Ranks open incidents by score, people affected, reported time
│   ├── recommendations.py  # Rule-based resource matching (prototype suggestions)
│   ├── incident_repository.py  # All SQL for incidents (save, list, fill missing scores)
│   ├── resource_repository.py  # All SQL for resources (save, list, available)
│   ├── recommendation_repository.py  # All SQL for recommendations (save, list)
│   ├── errors.py           # Turns validation errors into a short {field, message} list
│   └── routers/            # Endpoints, grouped by topic
│       ├── __init__.py
│       ├── health.py       # GET /health – is the server and database OK?
│       ├── alerts.py       # /api/alerts – sync, list, source status and review
│       ├── incidents.py    # POST/GET /api/incidents, /priority, /{id}/recommendation, /{id}/history
│       ├── resources.py    # POST/GET /api/resources
│       └── recommendations.py  # GET /api/recommendations/{id}, POST /{id}/decision
├── data/                   # The SQLite file (relief.db) is created here automatically
│   └── .gitkeep
├── examples/
│   ├── incident_flood.json    # Sample incident (scores High, 55)
│   ├── incident_low.json      # Sample incident (scores Low, 20)
│   ├── incident_high.json     # Sample incident (scores High, 70)
│   ├── incident_critical.json # Sample incident (scores Critical, 90)
│   ├── resource_ambulance.json # Sample ambulance resource
│   ├── resource_shelter.json  # Sample shelter resource
│   ├── decision_approve.json  # Sample operator approval
│   └── decision_reject.json   # Sample operator rejection
├── tests/
│   ├── __init__.py
│   ├── conftest.py         # Gives each test its own temporary database
│   ├── test_health.py      # Tests for /health and /
│   ├── test_incidents.py   # Tests for creating, listing, validating and scoring incidents
│   ├── test_severity.py    # Tests for the scoring rules themselves
│   ├── test_prioritization.py # Tests for open-incident priority ordering
│   ├── test_resources.py   # Tests for registering and listing resources
│   ├── test_recommendations.py # Tests for generating and saving recommendations
│   ├── test_decisions.py   # Tests for operator decisions and action history
│   └── test_database.py    # Tests for constraints, versioned migrations, and rollbacks
├── requirements.txt        # Python packages to install
├── .gitignore              # Files Git should ignore (venv, cache, database)
└── README.md               # This file
```

**Where future features will go:** new endpoint groups go in `app/routers/`
(e.g. `incidents.py`), and new database tables are created in
`init_database()` inside `app/database.py`.

---

## Requirements

- Windows 10/11
- Python 3.10 or newer (check with `python --version`)

---

## Setup (Windows PowerShell)

Run these commands from the project root folder.

```powershell
# 1. Go into the backend folder
cd backend

# 2. Create a virtual environment (a private folder for this project's packages)
python -m venv .venv

# 3. Activate it
.\.venv\Scripts\Activate.ps1

# 4. Install dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt
```

> **If activation fails** with "running scripts is disabled on this system", run
> this once and then try step 3 again:
> ```powershell
> Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
> ```
> Using Command Prompt (cmd) instead? Activate with `.venv\Scripts\activate.bat`.

---

## Run the server

With the virtual environment activated, inside `backend/`:

```powershell
uvicorn app.main:app --reload
```

`--reload` restarts the server automatically when you save a code change.
Stop the server with **Ctrl + C**.

---

## Verify it works

With the server running, open a **second** PowerShell window:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

or with curl:

```powershell
curl.exe http://127.0.0.1:8000/health
```

Expected response:

```json
{
  "status": "ok",
  "app": "Autonomous Multi-Agent Disaster Relief & Emergency Dispatch Engine",
  "version": "0.5.0",
  "database": "connected",
  "mode": "academic-prototype"
}
```

You can also open these in a browser:

| URL                              | What it shows                          |
|----------------------------------|----------------------------------------|
| http://127.0.0.1:8000/health     | Health-check JSON                      |
| http://127.0.0.1:8000/docs       | Interactive API documentation (Swagger) |

---

## Incidents API

| Method | URL                      | What it does                                     |
|--------|--------------------------|--------------------------------------------------|
| POST   | `/api/incidents`         | Validate and save a new incident (status `open`) |
| GET    | `/api/incidents`         | List all saved incidents, oldest first           |
| GET    | `/api/incidents/priority`| Open incidents ordered by priority, highest first |
| GET    | `/api/incidents/{id}`    | Retrieve a single incident by ID                 |

### Fields

| Field             | Type             | Required | Rules |
|-------------------|------------------|----------|-------|
| `hazard_type`     | text             | yes      | One of: `flood`, `earthquake`, `fire`, `cyclone`, `landslide`, `building_collapse`, `chemical_spill`, `other` |
| `description`     | text             | yes      | 10–1000 characters |
| `location`        | text             | yes      | 2–200 characters (free text, e.g. "Ward 12, Riverside Road") |
| `reported_at`     | date-time        | yes      | ISO 8601, e.g. `2026-11-19T10:30:00+05:30`; not in the future |
| `people_affected` | whole number     | yes      | 0 – 1,000,000 (an estimate) |
| `help_needed`     | list of text     | yes      | At least one, no duplicates. Each one of: `rescue`, `medical`, `evacuation`, `shelter`, `food`, `water`, `firefighting`, `other` |
| `latitude`        | decimal number   | optional | `-90` to `90` (must be paired with `longitude`) |
| `longitude`       | decimal number   | optional | `-180` to `180` (must be paired with `latitude`) |

The server sets `id`, `status` (always `"open"` for now) and `created_at`.
Clients cannot send these; unknown fields are rejected.

### Create an incident (PowerShell)

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/incidents -H "Content-Type: application/json" -d "@examples/incident_flood.json"
```

### List incidents

```powershell
curl.exe http://127.0.0.1:8000/api/incidents
```

### Validation errors

Invalid requests get HTTP **422** with one entry per problem:

```json
{
  "detail": "Validation failed",
  "errors": [
    {"field": "people_affected", "message": "Input should be greater than or equal to 0"},
    {"field": "location", "message": "Field required"}
  ]
}
```

### Data persistence

Incidents are stored in `data/relief.db`. Restarting the server keeps them.
To start over with an empty database, stop the server and delete that file —
it is recreated automatically on the next start.

---

## Severity scoring (prototype)

> [!WARNING]
> The severity score is an **unvalidated prototype estimate** made from simple
> demonstration rules. It is **not real emergency guidance**. A human operator
> must review every incident.

Every incident is scored automatically when it is created. The rules live in
[`app/severity.py`](app/severity.py) and add up two factors (0–100 total):

**Factor 1 – people affected (0–60 points)**

| People affected | Points |
|-----------------|--------|
| 0               | 0      |
| 1–9             | 10     |
| 10–49           | 25     |
| 50–199          | 40     |
| 200–999         | 50     |
| 1000+           | 60     |

**Factor 2 – immediate help needed (10–40 points)**
"Immediate" help types: `rescue`, `medical`, `evacuation`, `firefighting`.

| Help requested                                    | Points |
|---------------------------------------------------|--------|
| Only basic needs (`shelter`, `food`, `water`, `other`) | 10 |
| One immediate help type                           | 30     |
| Two or more immediate help types                  | 40     |

**Level:** 0–24 **Low** · 25–49 **Medium** · 50–74 **High** · 75–100 **Critical**

Each incident in the API response includes a `severity` object:

```json
"severity": {
  "score": 70,
  "max_score": 100,
  "level": "High",
  "explanation": "Score 70/100 (High): 120 people affected (+40); immediate help needed: medical (+30)",
  "factors": [
    {"factor": "people_affected", "points": 40, "max_points": 60, "reason": "120 people affected"},
    {"factor": "immediate_help", "points": 30, "max_points": 40, "reason": "immediate help needed: medical"}
  ],
  "rules_version": "demo-rules-v1",
  "disclaimer": "Unvalidated prototype estimate for an academic demonstration. Not real emergency guidance. A human operator must review it."
}
```

The score, level, explanation, factors and rules version are saved in the
database (`severity_*` columns). Clients cannot send their own severity.

**Older databases:** when the server starts it adds any missing `severity_*`
columns and scores incidents that were saved before scoring existed. No
existing data is deleted.

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/incidents -H "Content-Type: application/json" -d "@examples/incident_low.json"
curl.exe -X POST http://127.0.0.1:8000/api/incidents -H "Content-Type: application/json" -d "@examples/incident_high.json"
```

---

## Resources API

| Method | URL              | What it does                               |
|--------|------------------|--------------------------------------------|
| POST   | `/api/resources` | Validate and save a new resource           |
| GET    | `/api/resources` | List all registered resources, oldest first |

### Fields (all required)

| Field                 | Type         | Rules |
|-----------------------|--------------|-------|
| `resource_type`       | text         | One of: `ambulance`, `rescue_team`, `shelter`, `supply`, `other` |
| `name`                | text         | 2–120 characters (e.g. `"City Hospital Ambulance Unit A"`) |
| `quantity_available`  | whole number | 0 – 1,000,000 |
| `location`            | text         | 2–200 characters (free text, e.g. `"Central Depot, Ward 4"`) |
| `availability_status` | text         | One of: `available`, `limited`, `unavailable` |

The server sets `id` and `created_at`. Unknown fields are rejected.

### Add and list resources (PowerShell)

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/resources -H "Content-Type: application/json" -d "@examples/resource_ambulance.json"
curl.exe http://127.0.0.1:8000/api/resources
```

---

## Resource recommendations (prototype)

> [!WARNING]
> Recommendations use simple demonstration rules and are **not real emergency
> guidance**. Generating a recommendation saves it with status `"pending"` and
> **does not reduce resource quantities** — a human operator must review it.

| Method | URL                                      | What it does |
|--------|------------------------------------------|--------------|
| POST   | `/api/incidents/{incident_id}/recommendation` | Match the incident's `help_needed` with available resources and save a `"pending"` recommendation |

### Matching rules (`app/recommendations.py`)

- `medical` -> `ambulance`
- `rescue`, `evacuation`, `firefighting` -> `rescue_team`
- `shelter` -> `shelter`
- `food`, `water` -> `supply`
- `other` -> `other`

Only resources with `availability_status = "available"` and `quantity_available > 0`
are considered, and the suggested quantity never exceeds what is available.
Completely missing resource types are listed under `unavailable_needs`, and partial
stock shortfalls are listed under `insufficient_needs`.

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/incidents/1/recommendation
```

---

## Operator decisions & action history (prototype)

| Method | URL                                           | What it does |
|--------|-----------------------------------------------|--------------|
| POST   | `/api/recommendations/{recommendation_id}/decision` | Record `"approved"` or `"rejected"` + optional `note`, and add an `action_history` row |
| GET    | `/api/recommendations/{recommendation_id}`    | View a recommendation and its recorded decision |
| GET    | `/api/incidents/{incident_id}/history`        | View all recommendations and operator action history for an incident |

Resource quantities are **not changed** when approving or rejecting — decisions
are recorded for prototype review and auditability only.

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/recommendations/1/decision -H "Content-Type: application/json" -d "@examples/decision_approve.json"
curl.exe http://127.0.0.1:8000/api/recommendations/1
curl.exe http://127.0.0.1:8000/api/incidents/1/history
```

---

## Database schema, migrations & backup

All data is stored in `backend/data/relief.db` using Python's built-in `sqlite3`.
Foreign-key enforcement (`PRAGMA foreign_keys = ON`) is enabled on every connection.

### Tables & relationships

| Table | Key constraints & relationships |
|---|---|
| `incidents` | `id` PK; `people_affected >= 0`; `status IN ('open', 'resolved', 'closed')`; paired optional `latitude` (`-90..90`) and `longitude` (`-180..180`); `severity_*` columns. Indexed on `status`. |
| `resources` | `id` PK; `quantity_available >= 0`; `availability_status IN ('available', 'limited', 'unavailable')`; optional paired latitude/longitude coordinates added by migration 006. |
| `recommendations` | `id` PK; `incident_id` FK → `incidents(id)`; `status IN ('pending', 'approved', 'rejected')`; JSON `unavailable_needs` & `insufficient_needs` (unmatched gaps); `decision_note`, `decided_at`. Indexed on `incident_id`. |
| `recommendation_items` | `id` PK; `recommendation_id` FK → `recommendations(id)`; `resource_id` FK → `resources(id)`; `recommended_quantity > 0`; `available_quantity >= 0`; `for_help_needed` (JSON list); `explanation`; optional `distance_km` and `distance_basis`; `UNIQUE (recommendation_id, resource_id)`. Indexed on `recommendation_id` and `resource_id`. |
| `action_history` | `id` PK; `incident_id` FK → `incidents(id)`; `recommendation_id` FK → `recommendations(id)`; `decision IN ('approved', 'rejected')`; optional `note`, `created_at`. Indexed on `incident_id` and `recommendation_id`. |
| `external_alerts` | Provider-keyed public alerts; unique `(source, source_event_id)`; coordinates and review-status constraints. |
| `alert_sync_runs` | Per-provider sync history, counts, status, timestamps and safe error summary. |
| `alert_assessments` | Immutable, foreign-key-linked snapshots of the five specialist-agent assessment outputs. |
| `response_plans` | Human-gated plan state (`pending`, `simulated`, `rejected`, `completed`) linked to an incident and approved recommendation. |
| `response_plan_items` | Snapshot of proposed resource assignments; reservation quantity is counted only while the parent plan is `simulated`. |
| `response_plan_actions` | Append-only audit events for creation, simulation approval/rejection, and completion. |
| `schema_migrations` | Tracks applied migration versions (`version` PK, `name`, `applied_at`). |

### How to back up the database before upgrading

Stop the server first, then copy `data\relief.db` in PowerShell:

```powershell
cd backend
Copy-Item data\relief.db "data\relief.backup.$(Get-Date -Format 'yyyyMMdd-HHmmss').db"
```

### How migrations run

On server startup, `init_database()` calls `migrations.run_migrations()`:
- Applied versions are recorded in `schema_migrations`, so restarting the server skips already-applied migrations.
- For pre-upgrade databases missing `CHECK`/`FOREIGN KEY` constraints or newer columns, migration `002` checks existing rows first, then rebuilds outdated tables inside a single SQLite transaction while preserving all rows and IDs, and recreates all indexes.
- Migration `003` creates the relational `recommendation_items` table and migrates existing JSON matched items from `recommendations.items` (preserving the legacy JSON column untouched). If any legacy item references a missing `resource_id` or has invalid quantities, migration halts with `DatabaseMigrationError` without losing data.
- Multi-table writes (such as saving a recommendation + its `recommendation_items`, or recording an operator decision + `action_history`) run inside an explicit transaction and roll back completely if any step fails.

### What happens if existing data prevents a migration

Before rebuilding any table, the migration checks for rows that violate the new rules (e.g. negative `people_affected`, negative `quantity_available`, invalid status/decision text, or orphan foreign keys). If any invalid rows exist:
- Startup stops with a `DatabaseMigrationError` listing the exact table(s) and row ID(s).
- **No rows are deleted or silently altered.**
- Back up `data\relief.db`, fix or remove the reported rows, and start the server again.

---

## Run the automated tests

```powershell
pytest
```


---

## External disaster alerts: GDACS and USGS

External alerts are stored separately from confirmed or manually entered incidents.
The ingestion layer retains provider event IDs and raw payloads, and uses a unique
source/event key to avoid duplicates on repeat syncs. Refreshing an alert does not
overwrite its human review status or note.

| Method | URL | Purpose |
|---|---|---|
| POST | /api/alerts/sync | Manually sync one or both public feeds |
| GET | /api/alerts | List/filter imported alerts |
| GET | /api/alerts/sources | Show providers and their last sync result |
| POST | /api/alerts/{alert_id}/review | Mark an alert reviewed or dismissed |

### Sync the public feeds (Linux/macOS shell)

Run with the backend server active:

```bash
curl -X POST http://127.0.0.1:8000/api/alerts/sync \
  -H 'Content-Type: application/json' \
  -d '{"sources":["gdacs","usgs"]}'
```

### Inspect alerts and feed status

```bash
curl 'http://127.0.0.1:8000/api/alerts?limit=50'
curl http://127.0.0.1:8000/api/alerts/sources
```

### Record an operator review

```bash
curl -X POST http://127.0.0.1:8000/api/alerts/1/review \
  -H 'Content-Type: application/json' \
  -d '{"status":"reviewed","note":"Checked against the source bulletin."}'
```

Allowed review statuses are reviewed and dismissed. New alerts start as new.
A review does not automatically create an incident, assign resources, contact
responders, or dispatch anything.

GDACS provides a public multi-hazard GeoJSON event API. The USGS summary feed
used here provides all earthquakes from the past day. Provider availability
and refresh cadence are controlled by the providers; this prototype syncs only
when the API endpoint is called.

### Migration 004

Migration 004 creates external_alerts and alert_sync_runs without rebuilding
or deleting any existing incident, resource, or recommendation data.

---

---

## Multi-agent assessment (Stage 2)

Five specialist agents analyze an imported alert:

- **Evidence quality:** measures field completeness only. It is not a truth score or probability.
- **Hazard signal:** retains provider-native signals. GDACS Red/Orange/Green is shown as reported; USGS magnitude is not converted into a universal damage grade.
- **Event recency:** calculates the event age and flags implausible future timestamps.
- **Location evidence:** records coordinates or text-only location. Population exposure stays unknown until a real population/exposure dataset is connected.
- **Review coordinator:** creates an explainable human-review priority and records its reasons.

The orchestrator is deterministic and rule-based in this stage. No LLM or trained ML model is called. Every result requires human review and does not create incidents or dispatch resources.

| Method | URL | Purpose |
|---|---|---|
| POST | `/api/alerts/{alert_id}/assessments` | Run all five agents and save a snapshot |
| GET | `/api/alerts/{alert_id}/assessments` | List previous snapshots for an alert |
| GET | `/api/alerts/assessments/{assessment_id}` | Retrieve one saved assessment |

Run an assessment:

```bash
curl -X POST http://127.0.0.1:8000/api/alerts/1/assessments
```

List its history:

```bash
curl http://127.0.0.1:8000/api/alerts/1/assessments
```

Retrieve a specific assessment:

```bash
curl http://127.0.0.1:8000/api/alerts/assessments/1
```

Migration `005` adds `alert_assessments`, linked to `external_alerts` by a foreign key. Assessment records are immutable snapshots; re-running the agents creates a new history row instead of silently overwriting the previous result.

---

## Geographic resource planning (Stage 3)

Resource records accept optional coordinates. Both latitude and longitude must be provided together, and each is range-validated. Existing records remain valid with null coordinates.

The resource inventory form accepts coordinates and the dashboard map plots resource depots alongside incident markers. Marker colour distinguishes resource availability status.

### Nearby resource lookup

| Method | URL | Purpose |
|---|---|---|
| GET | `/api/resources/nearby?latitude=28.6139&longitude=77.2090&radius_km=25` | List available, geocoded resources inside a straight-line radius, nearest first |

The recommendation engine now ranks geocoded resources by Haversine distance when the incident has coordinates. Ungeocoded resources are retained as fallback candidates. If an incident has no coordinates, the prior stock-first ranking is retained. Each saved match records `distance_km` and `distance_basis`.

**Distance limitation:** Haversine distance is a great-circle straight-line estimate. It is not road distance, driving time, an accessible route, or a hazard footprint. This stage does not estimate population exposure or determine whether a resource is deployable.

Migration `006` adds optional `resources.latitude` / `resources.longitude` and the distance fields on `recommendation_items`. It uses additive column changes, preserving existing resource records and previously saved recommendations.

---

## Human-gated response plan simulation (Stage 4)

A plan is created from a recommendation only after that recommendation has an `approved` operator decision. New plans start as `pending`. A separate operator decision is required to approve the plan into `simulated` state or reject it. A simulated plan can later be completed; completion releases its simulation-only reservation.

| Method | URL | Purpose |
|---|---|---|
| POST | `/api/incidents/{incident_id}/response-plans` | Create pending plan from an approved recommendation |
| GET | `/api/response-plans` | List all plans; supports `?status=pending` |
| GET | `/api/response-plans/{plan_id}` | Get plan details and action history |
| POST | `/api/response-plans/{plan_id}/decision` | Approve into simulation or reject with a note |
| POST | `/api/response-plans/{plan_id}/complete` | Complete simulation and release reservation |

### Reservation accounting

- `resources.quantity_available` remains the physical quantity entered in the inventory register. The simulation workflow never changes it.
- Active reservations are calculated from `response_plan_items` whose parent plan is `simulated`.
- Resource API responses expose `simulation_reserved_quantity` and `simulation_remaining_quantity` separately.
- New resource recommendations use simulation-remaining quantities, not the physical total, so concurrent simulated plans cannot be double-booked.
- Rejected and completed plans do not hold reservations. A failed over-reservation approval returns HTTP 409 and leaves the plan pending.

**Safety boundary:** this is a college-project dispatch simulation. It does not contact emergency services, send vehicles/teams, notify responders, or guarantee real-world resource availability. The operator approval is not backed by user authentication or role-based access control. A trained human operator must verify real conditions independently.

---

## Alert Intelligence frontend (Stage 5)

The React application exposes the external alert workflow at `#/alerts`. The page reads `GET /api/alerts` and `GET /api/alerts/sources`, runs provider sync with `POST /api/alerts/sync`, records operator review through `POST /api/alerts/{id}/review`, and executes the specialist agents through `POST /api/alerts/{id}/assessments`.

The page refreshes its local API view every 60 seconds. It does **not** call the provider feeds on that timer; new external data is fetched only when an operator explicitly synchronizes the feeds.
