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
│   ├── incident_lifecycle_repository.py # Status transitions and operator timeline
│   ├── resource_repository.py  # All SQL for resources (save, list, available)
│   ├── recommendation_repository.py  # All SQL for recommendations (save, list)
│   ├── errors.py           # Turns validation errors into a short {field, message} list
│   └── routers/            # Endpoints, grouped by topic
│       ├── __init__.py
│       ├── health.py       # GET /health – is the server and database OK?
│       ├── alerts.py       # /api/alerts – sync, list, source status and review
│       ├── incidents.py    # Incident CRUD, priority, recommendations, lifecycle status and operational updates
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

- Windows 10/11, Linux, or macOS
- Python 3.10 or newer
- Git (for cloning the repository)

## Setup (Linux / macOS)

Run these commands from the repository root:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Then start the API from `backend/` with `uvicorn app.main:app --reload`. For the full application, the repository-root `./run.sh` launcher starts both the backend and frontend.

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
  "version": "0.9.0",
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

## Severity scoring (prototype rules v2)

> [!WARNING]
> The 0–100 severity score is an **unvalidated academic prototype estimate**.
> It is not a calibrated probability, verified risk score, or real emergency
> instruction. A human operator must review every incident.

Every incident is scored on creation and whenever the server starts with an old
or missing rules version. The rules live in [`app/severity.py`](app/severity.py)
and return six independently explained factors. Their maximum values sum to
100:

| Factor | Maximum | Prototype rule |
|---|---:|---|
| `people_affected` | 35 | 0: 0; 1–9: 8; 10–49: 18; 50–199: 25; 200–999: 30; 1000+: 35 |
| `immediate_help` | 20 | No immediate life-safety help: 5; one of rescue/medical/evacuation/firefighting: 15; two or more: 20 |
| `hazard_type` | 10 | Flood/fire/landslide: 8; earthquake/cyclone/building collapse: 10; chemical spill: 9; other: 3 |
| `hazard_signal` | 15 | Provider level green: 4, orange: 10, red: 15; earthquake magnitude, cyclone category/wind, or flood-water depth bands |
| `event_recency` | 15 | Under 1 hour: 15; up to 6 hours: 12; up to 24 hours: 9; up to 72 hours: 5; older/missing/future: 0 |
| `vulnerable_population` | 5 | Explicit mention of hospital, school, elderly, children, infants or care settings in description/location: 5; otherwise 0 |

When provider alert level and a supported measurement are both present, the
strongest applicable hazard-signal band is used once, not added together.
Earthquake values require a magnitude unit. Cyclone measurements accept integer
categories 1–5 or supported wind-speed units (km/h, knots, m/s, mph). Flood depth
accepts m, cm, mm or ft. The prototype depth bands are below 0.2 m: 0 points; 0.2–0.49 m:
4 points; 0.5–0.99 m: 10 points; 1 m or more: 15 points. Unsupported measurements
are retained in the incident record but receive no extra points.

The severity level thresholds are unchanged:
0–24 **Low** · 25–49 **Medium** · 50–74 **High** · 75–100 **Critical**.

The API response includes the numeric score, level, all six factors and their
reasons, rules version `demo-rules-v3`, and a clear prototype disclaimer.
Clients cannot submit their own severity score.

### Hazard-signal inputs

Manual incident requests may include optional `hazard_magnitude` and
`hazard_magnitude_unit` as a pair, plus optional `provider_alert_level`
(`green`, `orange`, or `red`). GDACS/USGS reviewed-alert promotion copies
available provider event time, alert level, value and unit into these fields automatically.
Values remain source evidence, not verified measurements.

### Existing database upgrade

Migration 012 adds the optional event time, magnitude, magnitude unit and provider alert-level incident columns. During startup,
`fill_missing_severity()` recomputes incidents whose saved rules version is
missing or not `demo-rules-v3`, using the data already stored. Incident IDs,
reported fields, status, recommendations and audit history are preserved.

### Affected-area priority

`GET /api/incidents/areas/priority` groups **open** incidents by their recorded
location text after trimming whitespace and matching case-insensitively. Areas
are ranked by highest individual severity score, then total reported people
affected, earliest first report, and top incident ID. The endpoint and main
dashboard explicitly disclose that no geocoding, region boundaries, or separate
population dataset is used.


---

## Resources API

| Method | URL              | What it does                               |
|--------|------------------|--------------------------------------------|
| POST   | `/api/resources` | Validate and save a new resource           |
| GET    | `/api/resources` | List all registered resources, oldest first |


### Update a resource and inspect its audit history

| Method | URL | Purpose |
|---|---|---|
| PATCH | `/api/resources/{resource_id}` | Update one or more resource fields and optionally provide an audit note |
| GET | `/api/resources/{resource_id}/history` | Return registration and inventory-change history |

Updates are partial. Latitude and longitude must be supplied together or cleared together. The service uses an immediate SQLite transaction to check current simulation reservations before changing stock. It rejects physical quantity reductions below active simulated reservations and rejects marking a reserved resource unavailable. Physical quantity is never reduced by a simulated plan.

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

The desired quantities are **demonstration assumptions only**: one rescue-team
unit per 200 people, one ambulance per 100 people, one shelter/supply unit per person,
and one other-resource unit per 25 people. They are not validated staffing ratios
or emergency-response guidance.

Only resources with an available status and positive unreserved quantity are
considered, and the suggested quantity never exceeds what is available. Missing
types are listed under unavailable_needs; partial shortages are listed under
insufficient_needs.

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
| `incidents` | `id` PK; `people_affected >= 0`; `status IN ('open', 'resolved', 'closed')`; paired optional `latitude` (`-90..90`) and `longitude` (`-180..180`); optional `event_at`, `hazard_magnitude`, `hazard_magnitude_unit`, `provider_alert_level`; `severity_*` columns. Indexed on `status`. |
| `resources` | `id` PK; `quantity_available >= 0`; `availability_status IN ('available', 'limited', 'unavailable')`; optional paired latitude/longitude coordinates added by migration 006. Physical quantity is kept separate from active simulation reservations. |
| `recommendations` | `id` PK; `incident_id` FK → `incidents(id)`; `status IN ('pending', 'approved', 'rejected')`; JSON `unavailable_needs` & `insufficient_needs` (unmatched gaps); `decision_note`, `decided_at`. Indexed on `incident_id`. |
| `recommendation_items` | `id` PK; `recommendation_id` FK → `recommendations(id)`; `resource_id` FK → `resources(id)`; `recommended_quantity > 0`; `available_quantity >= 0`; `for_help_needed` (JSON list); `explanation`; optional `distance_km` and `distance_basis`; `UNIQUE (recommendation_id, resource_id)`. Indexed on `recommendation_id` and `resource_id`. |
| `action_history` | `id` PK; `incident_id` FK → `incidents(id)`; `recommendation_id` FK → `recommendations(id)`; `decision IN ('approved', 'rejected')`; optional `note`, `created_at`. Indexed on `incident_id` and `recommendation_id`. |
| `external_alerts` | Provider-keyed public alerts; unique `(source, source_event_id)`; coordinates/review constraints; optional `linked_incident_id` and `linked_at` for human-approved promotion. |
| `alert_sync_runs` | Per-provider sync history, counts, status, timestamps and safe error summary. |
| `alert_assessments` | Immutable, foreign-key-linked snapshots of the five specialist-agent assessment outputs. |
| `response_plans` | Human-gated plan state (`pending`, `simulated`, `rejected`, `completed`) linked to an incident and approved recommendation. |
| `response_plan_items` | Snapshot of proposed resource assignments; reservation quantity is counted only while the parent plan is `simulated`. |
| `response_plan_actions` | Append-only audit events for creation, simulation approval/rejection, and completion. |
| `resource_change_history` | Registration/update audit records with JSON before/after values, optional note, timestamp, and a foreign key to `resources`. |\n| `incident_updates` | Immutable chronological incident status changes and operator notes, linked to `incidents`. |
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

The page refreshes its local API view every 60 seconds. The backend also synchronizes GDACS and USGS independently in the background when automatic sync is enabled (GDACS every 360 seconds and USGS every 60 seconds by default). The page timer itself does not call provider feeds; manual synchronization remains available.

---

## Promote a reviewed external alert into an incident (Stage 6)

| Method | URL | Purpose |
|---|---|---|
| POST | `/api/alerts/{alert_id}/promote` | Create and link one open incident from a reviewed alert |

Promotion is rejected with HTTP 409 unless the external alert is already `reviewed` and has no linked incident. The request body is the existing `IncidentCreate` schema: `hazard_type`, `description`, `location`, `reported_at`, `people_affected`, `help_needed`, and optional paired `latitude` / `longitude`.

The source alert and incident are updated inside one `BEGIN IMMEDIATE` transaction. The incident gets the existing prototype severity calculation and enters the existing incident priority workflow. The alert stores `linked_incident_id` and `linked_at`; a second promotion is rejected so one external event cannot create duplicate incidents.

The provider is not allowed to invent affected-person counts or help-needed values. An operator must supply or verify those fields. Promotion does not approve a recommendation, allocate resources, or dispatch anyone.

---

## Automatic public-feed synchronization (Stage 7)

On FastAPI startup, the lifespan starts one independent background loop per provider (when enabled). Each loop performs an initial sync, then waits for its configured interval. Defaults: GDACS 360 seconds and USGS 60 seconds. Synchronous network fetches run in worker threads; feed failures are recorded in `alert_sync_runs` and do not stop the other provider loop.

Automatic synchronization is enabled by default. Disable it for offline development:

```bash
RESQ_ALERT_AUTO_SYNC_ENABLED=false ./run.sh
```

Override refresh intervals (seconds):

```bash
RESQ_GDACS_SYNC_INTERVAL_SECONDS=600 RESQ_USGS_SYNC_INTERVAL_SECONDS=120 ./run.sh
```

Both intervals must be at least 30 seconds. `GET /api/alerts/sources` reports whether auto-sync is enabled and the configured interval. The browser's 60-second refresh only reloads local database content; provider data is refreshed by the backend loops. Manual sync remains available, and syncs for one provider are serialized.

---

## Resource readiness and inventory control (Stage 8)

Resource records can be maintained from the React inventory page. The backend accepts partial updates through `PATCH /api/resources/{resource_id}` and returns an audit trail through `GET /api/resources/{resource_id}/history`.

Editable fields: resource type, name, physical quantity, depot location, availability status, and paired optional coordinates. Each registration/update is recorded with before/after values, timestamp, and optional note in `resource_change_history`.

### Simulation reservation safeguards

- Physical `quantity_available` is never rewritten by a simulated response plan.
- An inventory edit cannot reduce physical quantity below active simulated reservations.
- A resource cannot be marked unavailable while a simulation reserves units from it.
- The API uses `BEGIN IMMEDIATE` so the reservation check and inventory update are serialized with simulation approvals.
- The UI displays physical quantity, simulation-reserved quantity, and simulation-remaining quantity separately.

Migration `009` creates the audit table. Existing resources are preserved; earlier registrations are not backfilled into this new history table because their original change details were not stored.

---

## Incident operations lifecycle (Stage 9)

| Method | URL | Purpose |
|---|---|---|
| PATCH | `/api/incidents/{incident_id}/status` | Change incident status and append a status-history event |
| POST | `/api/incidents/{incident_id}/updates` | Append an operator note |
| GET | `/api/incidents/{incident_id}/updates` | Return chronological operational history and count of active simulated plans |

Allowed lifecycle transitions are `open → resolved`, `resolved → open` (reopen), and `resolved → closed`. Closed incidents are terminal. Repeating the current status or skipping directly from open to closed returns HTTP 409.

An incident cannot be closed while it has one or more response plans in `simulated` state. Complete those simulation plans first. This check and status update run in one SQLite `BEGIN IMMEDIATE` transaction.

Status changes and operator notes are stored in `incident_updates`. Notes on closed incidents are rejected. These are operator-entered prototype records; they do not independently verify field conditions or responder attendance. The application does not yet authenticate operator identities.


---

## Incident-level AI-assisted agents (Phase 1)

The external-alert assessment described above is still deterministic. Phase 1 adds a separate incident-level pipeline with five named agents:

1. **MonitoringAgent** — reviews the existing incident and any linked normalized GDACS/USGS alert; produces a draft classification and incident summary for human verification.
2. **SeverityAgent** — exposes the existing deterministic severity score and factor breakdown; an LLM can add explanation only.
3. **PrioritizationAgent** — applies the existing deterministic severity → people affected → report time → ID order; an LLM cannot change ranks.
4. **ResourceAllocationAgent** — calls the existing nearest/available stock matcher and records proposals and shortfalls; an LLM cannot modify allocation IDs or quantities.
5. **NotificationAgent** — summarizes prior agent results and states the next operator review step.

The agents return AgentResult objects with name, mode (llm or rules), structured output, rationale, confidence field, and duration. The confidence field is an uncalibrated prototype indicator, not a probability.

### API

| Method | URL | Purpose |
|---|---|---|
| POST | /api/incidents/{incident_id}/agent-runs | Run and persist the five-agent pipeline |
| GET | /api/incidents/{incident_id}/agent-trace | Read recent immutable trace snapshots |

Each trace stores a privacy-minimized input summary, all agent outputs and modes, the coordinator summary, engine version, timing and creation timestamp. Migration 011 creates incident_agent_runs and its incident lookup index. Migration 012 adds optional event time and hazard-signal metadata to incidents and remains additive.

### Optional OpenAI-compatible LLM

The LLM provider is off unless LLM_ENABLED=true. No new dependency was added: the client uses the existing httpx package and calls POST {LLM_BASE_URL}/chat/completions. It requests JSON mode and validates the response against a strict Pydantic schema. All exceptions, timeouts, malformed JSON, and validation failures fall back to deterministic rules.

| Environment variable | Default |
|---|---|
| LLM_ENABLED | false |
| LLM_BASE_URL | https://api.openai.com/v1 |
| LLM_API_KEY | empty |
| LLM_MODEL | gpt-4o-mini |
| LLM_TIMEOUT_SECONDS | 8 |

The repository root contains .env.example as a reference only; FastAPI does not load it automatically. Export the variables in the server process environment. Never commit API keys. With LLM disabled or unavailable, the backend runs fully offline.

### Run one incident through the agents

~~~bash
curl -X POST http://127.0.0.1:8000/api/incidents/1/agent-runs
curl http://127.0.0.1:8000/api/incidents/1/agent-trace
~~~

The Incident Details page exposes this as **Run Agent Pipeline** and shows an **Agent Activity** timeline. The run is analysis-only: it does not create or modify incidents, save a resource recommendation, approve a plan, modify physical stock, or dispatch a team. Existing operator gates remain intact.


---

## Automatic dispatch simulation (Phase 3)

**Off by default.** Set `RESQ_ALLOW_AUTO_DISPATCH=true` to allow it; otherwise
switching to `auto` returns 409 and a saved `auto` setting is ignored.

Migration 013 adds a singleton dispatch settings row (default `manual`, not
paused, minimum severity `High`), a per-resource deployment ledger, dispatch
audit events, and a `dispatch_mode` field on response plans.

When the operator switches to `auto`, each eligible open incident runs the
five-agent pipeline and the deterministic resource matcher. The matcher’s
recommended quantities are then revalidated in a single SQLite
`BEGIN IMMEDIATE` transaction. Recommendation approval, response-plan rows,
active reservations, deployment assignments and `system-auto` audit events
commit together or roll back together. AUTO assignments remain virtual:
`quantity_available` is not physically decremented. The API separately reports
`simulation_reserved_quantity`, `simulation_remaining_quantity` and
`deployed_quantity`.

The `minimum_severity` setting accepts `High` (High or Critical) or
`Critical`. MANUAL remains the default. The pause switch blocks new automatic
assignments and retry attempts. Complete and Recall release reservations and
preserve deployment lifecycle audit events. When stock is added or increased,
the service retries shortfalls in deterministic priority order and subtracts
previously active deployed quantities before proposing additional units.

### API and safety checks

| Method | URL | Purpose |
|---|---|---|
| GET/PATCH | `/api/dispatch/settings` | Persist mode, severity threshold and emergency pause |
| GET | `/api/dispatch/deployments` | Inspect incident-linked AUTO assignments |
| GET | `/api/dispatch/audit` | Inspect actor-labelled dispatch audit events |
| POST | `/api/dispatch/incidents/{id}/retry` | Retry a previously recorded shortfall |
| POST | `/api/response-plans/{id}/recall` | Recall an active AUTO assignment |
| POST | `/api/response-plans/{id}/complete` | Complete a simulated assignment |

All AUTO output is a simulation only. It does not contact emergency services,
send notifications, move real responders, or modify physical inventory.


---

## Real-time event stream (Phase 4)

\`GET /api/events/stream\` is a FastAPI Server-Sent Events endpoint backed by
\`app/event_hub.py\`. The thread-safe hub sends bounded, JSON-safe invalidation
events after committed alert, incident, recommendation, resource, response-plan,
dispatch-setting and agent-run changes. Subscribers are removed when their
stream closes. A slow subscriber drops its oldest queued event rather than
blocking application writes.

SSE messages are notifications, not authoritative records. The frontend fetches
current data through REST. EventSource reconnects automatically, with a
10-second REST polling fallback while unavailable. The hub is in-process only;
multi-worker deployments require shared messaging to fan out events.

## Intake workflow, alerts and action log

Every new incident is normalised by the Monitoring agent, run through the five
agents, and given a pending recommendation (`app/incident_workflow.py`).

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/alerts` | Imported feed alerts, plus `active_alerts` and `recent_activity` |
| GET | `/api/activity` | Full action log; filter by `incident_id` or `alert_type` |
| POST | `/api/actions/{id}/decision` | Synopsis path; `{id}` is the recommendation ID |

Migration 014 adds the `action_log` table, copies existing history into it and
adds triggers that record new actions. For external alerts reviewed before the
upgrade, only the latest review was stored, so only that one is copied.
Open incidents are re-scored on every read so recency stays current; resolved
and closed incidents keep their score from the time they left the open state.
