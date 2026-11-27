import React, { useMemo, useState } from "react";
import { completeResponsePlan } from "../../services/responsePlanService";
import { recallResponsePlan } from "../../services/dispatchService";
import { formatDateTime, formatNumber, labelize } from "../../utils/format";
import Icon from "../common/Icon";

const RESOURCE_TYPES = [
  { key: "rescue_team", label: "Rescue teams" },
  { key: "ambulance", label: "Ambulances" },
  { key: "shelter", label: "Shelters" },
  { key: "supply", label: "Supplies" },
];

function alertTone(level) {
  const value = String(level || "").toLowerCase();
  return ["red", "orange", "green"].includes(value) ? value : "unknown";
}

function dateValue(value) {
  const parsed = value ? new Date(value).getTime() : 0;
  return Number.isFinite(parsed) ? parsed : 0;
}

function ResourceAvailability({ resources, plans }) {
  const activePlans = plans.filter((plan) => plan.status === "simulated");
  const rows = RESOURCE_TYPES.map((type) => {
    const available = resources
      .filter((resource) => resource.resource_type === type.key && resource.availability_status === "available")
      .reduce((sum, resource) => sum + Number(resource.simulation_remaining_quantity ?? resource.quantity_available ?? 0), 0);
    const deployed = activePlans.reduce((sum, plan) => (
      sum + (plan.items || [])
        .filter((item) => item.resource_type === type.key)
        .reduce((itemSum, item) => itemSum + Number(item.assigned_quantity || 0), 0)
    ), 0);
    return { ...type, available, deployed };
  });

  return (
    <section className="surface-card live-panel">
      <div className="panel-header">
        <div>
          <h2 className="section-title">Resource Availability</h2>
          <p className="section-subtitle">Unreserved inventory and units assigned to active simulations.</p>
        </div>
        <Icon name="package" size={18} />
      </div>
      <div className="resource-availability-list">
        {rows.map((row) => (
          <div className="resource-availability-row" key={row.key}>
            <span>{row.label}</span>
            <strong className="tabular">{formatNumber(row.available)}</strong>
            <span className="resource-availability-meta">available</span>
            <strong className="tabular">{formatNumber(row.deployed)}</strong>
            <span className="resource-availability-meta">deployed</span>
          </div>
        ))}
      </div>
      <p className="live-panel-footnote">Available excludes limited/unavailable pools. Counts use local inventory and virtual reservations, not live agency inventories.</p>
    </section>
  );
}

function ActiveOperations({ plans, onRefresh }) {
  const [busyId, setBusyId] = useState(null);
  const [error, setError] = useState("");
  const activePlans = plans
    .filter((plan) => plan.status === "simulated")
    .slice()
    .sort((a, b) => dateValue(b.created_at) - dateValue(a.created_at));

  const act = async (plan, action) => {
    setBusyId(plan.id);
    setError("");
    try {
      if (action === "recall") await recallResponsePlan(plan.id, "Recalled from the live dashboard.");
      else await completeResponsePlan(plan.id, "Completed from the live dashboard.");
      await onRefresh();
    } catch (err) {
      setError(err.message || "The operation could not be updated.");
    } finally {
      setBusyId(null);
    }
  };

  return (
    <section className="surface-card live-panel">
      <div className="panel-header">
        <div>
          <h2 className="section-title">Active Rescue Operations</h2>
          <p className="section-subtitle">Approved response-plan assignments currently active in the simulation.</p>
        </div>
        <span className="live-count">{activePlans.length} active</span>
      </div>
      {error && <p className="inline-error" role="alert">{error}</p>}
      {activePlans.length === 0 ? (
        <div className="live-empty">No active response-plan simulations yet.</div>
      ) : (
        <div className="active-operations-list">
          {activePlans.map((plan) => {
            const units = (plan.items || []).reduce((sum, item) => sum + Number(item.assigned_quantity || 0), 0);
            const names = [...new Set((plan.items || []).map((item) => item.resource_name).filter(Boolean))];
            const distances = (plan.items || []).map((item) => item.distance_km).filter((value) => typeof value === "number");
            const distanceLabel = distances.length
              ? `Nearest assigned resource: ${Math.min(...distances).toFixed(1)} km straight-line`
              : "Distance not recorded";
            return (
              <article className="active-operation" key={plan.id}>
                <div className="active-operation-heading">
                  <div>
                    <strong>Plan #{plan.id} · Incident #{plan.incident_id}</strong>
                    <span className={`operation-mode operation-mode-${plan.dispatch_mode || "manual"}`}>
                      {String(plan.dispatch_mode || "manual").toUpperCase()} SIMULATION
                    </span>
                  </div>
                  <span className="operation-status">SIMULATED</span>
                </div>
                <p>{units} assigned unit(s) · {names.slice(0, 3).join(", ") || "Resource assignment recorded"}</p>
                <p className="active-operation-distance">{distanceLabel} · ETA unavailable (not calculated)</p>
                <div className="active-operation-actions">
                  {plan.dispatch_mode === "auto" && (
                    <button type="button" className="btn btn-secondary btn-sm" disabled={busyId === plan.id} onClick={() => act(plan, "recall")}>
                      {busyId === plan.id ? "Working..." : "Recall"}
                    </button>
                  )}
                  <button type="button" className="btn btn-primary btn-sm" disabled={busyId === plan.id} onClick={() => act(plan, "complete")}>
                    {busyId === plan.id ? "Working..." : "Complete"}
                  </button>
                </div>
              </article>
            );
          })}
        </div>
      )}
      <p className="live-panel-footnote">Distances are straight-line estimates only; no road travel time or ETA is calculated.</p>
    </section>
  );
}

function HazardChart({ incidents }) {
  const data = useMemo(() => {
    const counts = new Map();
    incidents.forEach((incident) => {
      const key = incident.hazard_type || "other";
      counts.set(key, (counts.get(key) || 0) + 1);
    });
    return [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 6);
  }, [incidents]);
  const max = Math.max(1, ...data.map(([, value]) => value));

  return (
    <section className="surface-card live-panel">
      <div className="panel-header">
        <div>
          <h2 className="section-title">Incidents by Hazard</h2>
          <p className="section-subtitle">Current saved incident records by reported hazard type.</p>
        </div>
        <Icon name="activity" size={18} />
      </div>
      {data.length === 0 ? (
        <div className="live-empty">No incident records to chart.</div>
      ) : (
        <svg className="hazard-chart" viewBox={`0 0 560 ${Math.max(110, data.length * 37 + 12)}`} role="img" aria-label="Bar chart of incident counts by hazard type">
          {data.map(([hazard, value], index) => {
            const y = index * 37 + 5;
            const width = (value / max) * 365;
            return (
              <g key={hazard}>
                <text x="0" y={y + 16} className="hazard-chart-label">{labelize(hazard)}</text>
                <rect x="150" y={y + 3} width={Math.max(width, 2)} height="19" rx="4" className="hazard-chart-bar" />
                <text x={158 + Math.max(width, 2)} y={y + 18} className="hazard-chart-value">{value}</text>
              </g>
            );
          })}
        </svg>
      )}
    </section>
  );
}

function LiveAlerts({ alerts, feedSources }) {
  const feedsOffline = feedSources.some((source) => source.status === "offline");
  const latest = alerts
    .slice()
    .sort((a, b) => dateValue(b.event_at || b.first_seen_at) - dateValue(a.event_at || a.first_seen_at))
    .slice(0, 8);

  return (
    <section className="surface-card live-panel">
      <div className="panel-header">
        <div>
          <h2 className="section-title">Live Alerts Feed</h2>
          <p className="section-subtitle">Newest GDACS and USGS reports saved by configured feed sync.</p>
        </div>
        <span className="live-count">{alerts.length} saved</span>
      </div>
      {feedsOffline && (
        <p className="feed-offline-indicator" role="status">
          Feeds offline - using saved/demo data
        </p>
      )}
      {latest.length === 0 ? (
        <div className="live-empty">No external alerts have been saved yet. Check Alert Intelligence or sync a feed.</div>
      ) : (
        <div className="live-alert-list">
          {latest.map((alert) => (
            <article className="live-alert-row" key={alert.id}>
              <div className="live-alert-heading">
                <strong>{alert.title}</strong>
                <span className={`alert-level-badge alert-level-${alertTone(alert.alert_level)}`}>
                  {alert.alert_level ? String(alert.alert_level).toUpperCase() : "UNRATED"}
                </span>
              </div>
              <div className="live-alert-meta">
                <span>{String(alert.source || "feed").toUpperCase()}</span>
                <span>{labelize(alert.hazard_type || alert.event_type || "unknown")}</span>
                <span>{alert.location || alert.country || "Location not supplied"}</span>
              </div>
              <time>{formatDateTime(alert.event_at || alert.first_seen_at)}</time>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

export default function DashboardLivePanels({ alerts = [], feedSources = [], incidents = [], resources = [], responsePlans = [], onRefresh }) {
  return (
    <div className="dashboard-live-grid">
      <LiveAlerts alerts={alerts} feedSources={feedSources} />
      <ResourceAvailability resources={resources} plans={responsePlans} />
      <ActiveOperations plans={responsePlans} onRefresh={onRefresh} />
      <HazardChart incidents={incidents} />
    </div>
  );
}
