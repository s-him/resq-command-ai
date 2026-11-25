# Backend – Autonomous Multi-Agent Disaster Relief & Emergency Dispatch Engine

> **Academic prototype for a college mini-project.**
> - Imports read-only public alert data from GDACS (multi-hazard) and USGS (earthquakes), alongside manually entered reports.
> - It is **not** a real emergency system and does **not** connect to emergency services or live dispatch systems.
> - It does **not** predict disasters.
> - A **human operator** must approve or reject every recommendation.

This backend provides a FastAPI API, SQLite persistence, manual incident reporting, prototype severity scoring, resource recommendations, operator decision logging, and read-only public alert ingestion. External alerts are stored separately from incidents until an operator reviews them.

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
  "version": "0.2.0",
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
| `resources` | `id` PK; `quantity_available >= 0`; `availability_status IN ('available', 'limited', 'unavailable')`. |
| `recommendations` | `id` PK; `incident_id` FK → `incidents(id)`; `status IN ('pending', 'approved', 'rejected')`; JSON `unavailable_needs` & `insufficient_needs` (unmatched gaps); `decision_note`, `decided_at`. Indexed on `incident_id`. |
| `recommendation_items` | `id` PK; `recommendation_id` FK → `recommendations(id)`; `resource_id` FK → `resources(id)`; `recommended_quantity > 0`; `available_quantity >= 0`; `for_help_needed` (JSON list); `explanation`; `UNIQUE (recommendation_id, resource_id)`. Indexed on `recommendation_id` and `resource_id`. |
| `action_history` | `id` PK; `incident_id` FK → `incidents(id)`; `recommendation_id` FK → `recommendations(id)`; `decision IN ('approved', 'rejected')`; optional `note`, `created_at`. Indexed on `incident_id` and `recommendation_id`. |
| `external_alerts` | Provider-keyed public alerts; unique `(source, source_event_id)`; coordinates and review-status constraints. |\n| `alert_sync_runs` | Per-provider sync history, counts, status, timestamps and safe error summary. |\n| `schema_migrations` | Tracks applied migration versions (`version` PK, `name`, `applied_at`). |

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
