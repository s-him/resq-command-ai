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

- **`backend/`** — Python **FastAPI** REST API + **SQLite** database (`sqlite3`) with explainable rule-based severity scoring, multi-factor open-incident prioritisation, a resource inventory register, resource recommendation matching, human operator decision logging, GDACS/USGS alert ingestion with deduplication and human review, a five-specialist explainable assessment pipeline, proximity-aware resource matching, a combined incident/resource map, and a human-gated response-plan simulation ledger, versioned database migrations (`001`–`007`), and a `pytest` test suite.
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
│   │   ├── agents/                    # Evidence, hazard, recency, location and review agents
│   │   ├── assessment_orchestrator.py # Runs agents and combines their findings
│   │   ├── assessment_repository.py   # Persists immutable assessment snapshots
│   │   ├── assessment_schemas.py      # Assessment API contracts
│   │   ├── routers/response_plans.py   # Response simulation API routes
│   │   ├── main.py                  # FastAPI entry point, lifespan DB init, and CORS config
│   │   ├── config.py                # Project-relative SQLite path (RELIEF_DATABASE_PATH override)
│   │   ├── database.py              # SQLite connection helper (PRAGMA foreign_keys = ON)
│   │   ├── migrations.py            # Versioned SQLite migrations (001-007)
│   │   ├── schemas.py               # Pydantic request/response schemas and validation rules
│   │   ├── severity.py              # Explainable 0–100 rule-based severity scoring
│   │   ├── prioritization.py        # Open-incident priority ranking & tie-breaker explanations
│   │   ├── recommendations.py       # Rule-based resource matching & shortfall reporting
│   │   ├── incident_repository.py   # Parameterized SQLite queries for incidents
│   │   ├── resource_repository.py   # Parameterized SQLite queries for resources
│   │   ├── recommendation_repository.py # Transactional queries for recommendations & action_history
│   │   ├── errors.py                # Structured 422 validation error formatter
│   │   └── routers/                 # /health, /api/incidents, /api/resources, /api/recommendations
│   ├── data/                        # relief.db is created here automatically on first startup
│   ├── examples/                    # Sample JSON request payloads for curl/PowerShell demos
│   ├── tests/                       # 150 automated pytest checks (each uses a temporary SQLite DB)
│   ├── requirements.txt             # Python dependencies
│   └── README.md                    # Detailed backend API & database schema reference
├── frontend/
│   ├── src/
│   │   ├── config.js                # Central API_BASE_URL configuration (VITE_API_BASE_URL)
│   │   ├── services/                # Central fetch() client and domain API service modules
│   │   ├── context/                 # Shared backend state (DataContext) and operation toasts
│   │   ├── components/              # Layout shell, common UI primitives, map, and forms
│   │   └── pages/                   # Dashboard, Incidents, IncidentDetails, Resources, Recommendations, ActivityHistory
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
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd "<PROJECT_FOLDER_NAME>"
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

> **Note on SQLite initialization:** You do **not** need an existing database file. On first startup, `uvicorn` automatically creates `backend/data/relief.db` and runs versioned migrations `001`–`007` to initialize all tables (`incidents`, `resources`, `recommendations`, `recommendation_items`, `action_history`, `external_alerts`, `alert_sync_runs`, `alert_assessments`, `response_plans`, `response_plan_items`, `response_plan_actions`, and `schema_migrations`).

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

**This is not a real dispatch system.** No emergency service is contacted, no team or vehicle is sent, and the physical `resources.quantity_available` value is never modified. Active simulated reservations reduce the `simulation_remaining_quantity` shown in inventory and used by subsequent recommendations, preventing overlapping simulations from overbooking the same registered stock.

| Method | URL | Purpose |
|---|---|---|
| POST | `/api/incidents/{incident_id}/response-plans` | Create a pending plan from an approved recommendation |
| GET | `/api/response-plans` | List plans (optional `?status=pending`) |
| GET | `/api/response-plans/{plan_id}` | Inspect a plan and its audit history |
| POST | `/api/response-plans/{plan_id}/decision` | Approve into simulation or reject |
| POST | `/api/response-plans/{plan_id}/complete` | Complete a simulation and release reservations |

The frontend exposes this workflow under **Dispatch Simulation**. Each plan records its resource assignments, operator decisions, notes and timestamps.
