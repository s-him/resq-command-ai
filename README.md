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

- **`backend/`** — Python **FastAPI** REST API + **SQLite** database (`sqlite3`) with explainable rule-based severity scoring, multi-factor open-incident prioritisation, a resource inventory register, resource recommendation matching, human operator decision logging, GDACS/USGS alert ingestion with deduplication and human review, versioned database migrations (`001`–`004`), and a `pytest` test suite.
- **`frontend/`** — **React 19** + **Vite 6** + **Leaflet** operational intelligence dashboard (**ResQ Command**) connected to the FastAPI backend.

```text
.
├── backend/
│   ├── app/
│   │   ├── alert_sources.py           # GDACS + USGS feed parsing and normalization
│   │   ├── alert_repository.py        # External-alert persistence, deduplication and review
│   │   ├── alert_service.py           # Feed synchronization orchestration
│   │   ├── alert_schemas.py           # External-alert API contracts
│   │   ├── main.py                  # FastAPI entry point, lifespan DB init, and CORS config
│   │   ├── config.py                # Project-relative SQLite path (RELIEF_DATABASE_PATH override)
│   │   ├── database.py              # SQLite connection helper (PRAGMA foreign_keys = ON)
│   │   ├── migrations.py            # Versioned SQLite migrations (001-004)
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
│   ├── tests/                       # 104 automated pytest checks (each uses a temporary SQLite DB)
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

> **Note on SQLite initialization:** You do **not** need an existing database file. On first startup, `uvicorn` automatically creates `backend/data/relief.db` and runs versioned migrations `001`–`004` to initialize all tables (`incidents`, `resources`, `recommendations`, `recommendation_items`, `action_history`, `external_alerts`, `alert_sync_runs`, and `schema_migrations`).

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
