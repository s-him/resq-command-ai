import React from "react";
import { useData } from "../../context/DataContext";
import { useNow } from "../../hooks/useNow";
import { formatDateTime, incidentCode } from "../../utils/format";
import Icon from "../common/Icon";

const ROUTE_META = {
  dashboard: { section: "Overview", title: "Operational Overview" },
  incidents: { section: "Operations", title: "Incident Management" },
  incident: { section: "Operations · Incidents", title: "Incident Investigation" },
  resources: { section: "Operations", title: "Resource Inventory" },
  recommendations: { section: "Operations", title: "Operator Decision Centre" },
  history: { section: "Monitoring", title: "Activity & Audit History" },
  notfound: { section: "Navigation", title: "Page Not Found" },
};

const CONNECTION_LABELS = {
  connected: "Connected",
  unavailable: "Connection unavailable",
  checking: "Checking connection",
};

export default function Topbar({ route, onOpenMobileNav, onOpenCreateIncident }) {
  const { health, refreshing, refreshAll } = useData();
  const now = useNow(30000);
  const meta = ROUTE_META[route.name] || ROUTE_META.dashboard;
  const title =
    route.name === "incident" && route.id
      ? `${meta.title} · ${incidentCode(route.id)}`
      : meta.title;

  return (
    <header className="topbar">
      <div className="topbar-left">
        <button
          type="button"
          className="icon-btn mobile-menu-btn"
          onClick={onOpenMobileNav}
          aria-label="Open navigation menu"
        >
          <Icon name="menu" size={20} />
        </button>
        <div>
          <div className="topbar-breadcrumb">{meta.section}</div>
          <h1 className="topbar-title">{title}</h1>
        </div>
      </div>

      <div className="topbar-right">
        <span className="sim-chip" title="Simulated or manually entered academic data only">
          Simulated / Reported Data
        </span>

        <div
          className={`conn-pill conn-pill-${health.state}`}
          role="status"
          title={health.error || "Verified via GET /health"}
        >
          <span className={`conn-dot conn-${health.state}`} aria-hidden="true" />
          <span>{CONNECTION_LABELS[health.state] || "Checking connection"}</span>
        </div>

        <span className="topbar-clock tabular" aria-label="Current local time">
          {formatDateTime(now)}
        </span>

        <button
          type="button"
          className="btn btn-secondary btn-sm"
          onClick={refreshAll}
          disabled={refreshing}
          title="Refresh data from FastAPI backend"
        >
          <Icon name="refresh" size={15} className={refreshing ? "spin" : ""} />
          <span>{refreshing ? "Syncing..." : "Refresh"}</span>
        </button>

        {onOpenCreateIncident && (
          <button
            type="button"
            className="btn btn-primary btn-sm"
            onClick={() => onOpenCreateIncident()}
          >
            <Icon name="plus" size={15} />
            <span>Report Incident</span>
          </button>
        )}
      </div>
    </header>
  );
}

