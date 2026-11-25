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
        ├── IncidentDetails.jsx          # Investigation workspace, severity meter, recommendations, decision centre, audit trail
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
