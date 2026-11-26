# Frontend – ResQ Command (Multi-Agent Disaster Relief & Emergency Dispatch Engine)

> **ACADEMIC PROTOTYPE | SIMULATED / REPORTED DATA ONLY | HUMAN REVIEW REQUIRED | NOT FOR REAL EMERGENCY DISPATCH**

A modular React 19 + Vite 6 operational intelligence frontend connected to the FastAPI + SQLite backend.

## Architecture & Directory Structure

```
frontend/
├── index.html                           # Application HTML shell
├── package.json                         # React 19, Leaflet, and Vite scripts
├── vite.config.js                       # Vite configuration (port 5173)
├── .env.example                         # Example backend URL override
└── src/
    ├── main.jsx                         # React root entry point
    ├── App.jsx                          # Top-level providers, shell, and hash router
    ├── config.js                        # Single API_BASE_URL configuration
    ├── styles.css                       # ResQ Command design system & responsive layout
    ├── context/
    │   ├── DataContext.jsx              # Shared backend state (health, priority, incidents, resources, history)
    │   └── ToastContext.jsx             # Frontend operation feedback toasts
    ├── hooks/
    │   ├── useHashRoute.js              # Lightweight hash router (#/, #/incidents, #/incidents/:id, #/resources, #/recommendations, #/history)
    │   └── useNow.js                    # Live clock hook
    ├── services/
    │   ├── apiClient.js                 # Central fetch() wrapper & FastAPI 422/404/409 error normalizer
    │   ├── healthService.js             # GET /health
    │   ├── incidentService.js           # GET/POST /api/incidents, /priority, /{id}, /{id}/history
    │   ├── resourceService.js           # GET/POST /api/resources
    │   └── recommendationService.js     # POST /api/incidents/{id}/recommendation, GET/POST /api/recommendations/{id}/decision
    ├── utils/
    │   ├── constants.js                 # Exact backend enum values, severity colors, and mandatory safety strings
    │   ├── format.js                    # Date/time, number, and code formatters (INC-0001, REC-0001, RES-0001)
    │   └── events.js                    # Builds chronological audit events from real backend records
    ├── components/
    │   ├── common/                      # Icon, Badge, Modal, ConfirmDialog, Skeleton, EmptyState, ErrorState
    │   ├── layout/                      # AppShell, Sidebar, Topbar, SafetyBanner
    │   ├── dashboard/                   # StatCard, WorkflowOverview, PriorityQueueTable
    │   └── incidents/                   # IncidentFormModal, IncidentMapPanel, SeverityPanel
    └── pages/
        ├── Dashboard.jsx                # Operational Overview (stats, workflow, priority queue, Leaflet map)
        ├── Incidents.jsx                # Full incident list with search, filters, and sort options
        ├── IncidentDetails.jsx          # Investigation workspace, agent activity, severity, recommendations, decisions, audit trail
        ├── Resources.jsx                # Category strip, resource cards, inventory table, Add Resource modal
        ├── Recommendations.jsx          # Global Operator Decision Centre across all incidents
        └── ActivityHistory.jsx          # Date-grouped chronological audit timeline
```

## Setup & Run (Windows PowerShell)

```powershell
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173** in your browser (with the FastAPI backend running at `http://127.0.0.1:8000`).


## Incident Agent Activity

Open an incident and select **Run Agent Pipeline** to run the five advisory incident agents. The **Agent Activity** section shows each agent's selected mode (llm or rules), rationale, confidence indicator, execution time, and structured result. The API stores run snapshots under GET /api/incidents/{id}/agent-trace.

LLM use is disabled by default and configured in the backend process environment. The frontend never receives or stores the provider API key. All agent outputs remain suggestions; the UI does not treat them as confirmation or dispatch authorization.


## Dispatch mode controls

The Dispatch Simulation page exposes the database-backed MANUAL/AUTO setting,
the minimum severity threshold and the emergency pause switch. MANUAL remains
the default. AUTO plans show their linked incident/resource assignments and
allow the operator to Complete or Recall them. All quantities are virtual
reservations in the prototype ledger; physical inventory is unchanged and no
real responder is contacted.


## Real-time dashboard (Phase 4)

\`DataContext\` owns one shared \`EventSource\` connection to
\`/api/events/stream\`. When a change notification arrives, it reloads the shared
incident, alert, area-priority, resource, response-plan and history data. Browser
reconnect is automatic; a 10-second REST polling fallback runs while SSE is
unavailable. The top bar displays LIVE, RECONNECTING or POLLING.

Dashboard live panels show the newest-first alert feed, resource units available
versus deployed, active simulated operations with Complete/Recall, and an SVG
incident-by-hazard chart. The existing Leaflet map continues to show incident
and resource markers. Distances are straight-line estimates; ETA is not calculated.
