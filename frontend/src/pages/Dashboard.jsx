import React, { useState } from "react";
import PriorityQueueTable from "../components/dashboard/PriorityQueueTable";
import StatCard from "../components/dashboard/StatCard";
import WorkflowOverview from "../components/dashboard/WorkflowOverview";
import AreaPriorityTable from "../components/dashboard/AreaPriorityTable";
import DashboardLivePanels from "../components/dashboard/DashboardLivePanels";
import { SkeletonStatCards } from "../components/common/Skeleton";
import Icon from "../components/common/Icon";
import IncidentMapPanel from "../components/incidents/IncidentMapPanel";
import { useData } from "../context/DataContext";
import { navigate } from "../hooks/useHashRoute";
import { formatDateTime, formatNumber } from "../utils/format";
import { runDemoScenario } from "../services/demoService";

export default function Dashboard({ onOpenCreateIncident }) {
  const [demoScenario, setDemoScenario] = useState("cyclone");
  const [demoRunning, setDemoRunning] = useState(false);
  const [demoFeedback, setDemoFeedback] = useState("");
  const [demoError, setDemoError] = useState("");

  const {
    priority,
    areaPriority,
    incidents,
    resources,
    alerts,
    responsePlans,
    recommendations,
    actions,
    lastUpdated,
    refreshing,
    refreshAll,
  } = useData();

  const openIncidents = priority.data?.incidents || [];
  const highCriticalCount = openIncidents.filter((inc) =>
    ["High", "Critical"].includes(inc.severity?.level)
  ).length;

  const availableResources = resources.data.filter(
    (res) => res.availability_status === "available" && (res.simulation_remaining_quantity ?? res.quantity_available) > 0
  );
  const totalAvailableUnits = availableResources.reduce(
    (sum, res) => sum + (res.simulation_remaining_quantity ?? res.quantity_available ?? 0),
    0
  );

  const pendingRecs = recommendations.filter((rec) => rec.status === "pending");

  const statsLoading =
    priority.loading &&
    incidents.loading &&
    resources.loading &&
    incidents.data.length === 0;

  const handleRunDemo = async () => {
    setDemoRunning(true);
    setDemoFeedback("");
    setDemoError("");
    try {
      const result = await runDemoScenario(demoScenario);
      await refreshAll();
      setDemoFeedback(result.message);
    } catch (error) {
      setDemoError(error.message || "The demo scenario could not be started.");
    } finally {
      setDemoRunning(false);
    }
  };

  return (
    <div className="page-stack">
      <section className="page-hero">
        <div>
          <h2 className="page-heading">Operational Overview</h2>
          <p className="page-subheading">
            Monitor reported incidents, assess operational priorities, and review resource
            recommendations.
          </p>
        </div>

        <div className="page-hero-actions">
          {lastUpdated && (
            <span className="last-sync tabular">
              Updated {formatDateTime(lastUpdated)}
            </span>
          )}
          <button
            type="button"
            className="btn btn-secondary"
            onClick={refreshAll}
            disabled={refreshing}
          >
            <Icon name="refresh" size={15} className={refreshing ? "spin" : ""} />
            <span>{refreshing ? "Refreshing..." : "Refresh"}</span>
          </button>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => onOpenCreateIncident()}
          >
            <Icon name="plus" size={15} />
            <span>Create Incident</span>
          </button>
        </div>
      </section>

      <section className="demo-launcher surface-card" aria-label="Simulated demo scenarios">
        <div className="demo-launcher-copy">
          <span className="demo-eyebrow">SIMULATED DATA</span>
          <h3>Run demo scenario</h3>
          <p>Inject a labeled sample event, run the agents and update the live dashboard. No real alerts or responders are involved.</p>
        </div>
        <div className="demo-launcher-controls">
          <label className="sr-only" htmlFor="demo-scenario">Choose a demo scenario</label>
          <select
            id="demo-scenario"
            className="demo-scenario-select"
            value={demoScenario}
            onChange={(event) => setDemoScenario(event.target.value)}
            disabled={demoRunning}
          >
            <option value="cyclone">Cyclone — Odisha coast</option>
            <option value="flood">Flood — Assam</option>
            <option value="earthquake">Earthquake — Northeast India</option>
          </select>
          <button
            type="button"
            className="btn btn-primary"
            onClick={handleRunDemo}
            disabled={demoRunning}
          >
            <Icon name={demoRunning ? "loader" : "play"} size={15} className={demoRunning ? "spin" : ""} />
            <span>{demoRunning ? "Running scenario..." : "Run demo scenario"}</span>
          </button>
        </div>
      </section>
      {(demoFeedback || demoError) && (
        <p className={`demo-feedback ${demoError ? "demo-feedback-error" : ""}`} role={demoError ? "alert" : "status"}>
          {demoError || demoFeedback}
        </p>
      )}

      {statsLoading ? (
        <SkeletonStatCards count={4} />
      ) : (
        <section className="stats-grid" aria-label="Operational summary statistics">
          <StatCard
            label="Open Incidents"
            value={priority.error ? "—" : formatNumber(openIncidents.length)}
            meta={`${formatNumber(incidents.data.length)} total reported in database`}
            icon="alert"
            indicator="blue"
            onClick={() => navigate("#/incidents")}
          />
          <StatCard
            label="High / Critical"
            value={priority.error ? "—" : formatNumber(highCriticalCount)}
            meta="Open incidents scoring 50/100 or above"
            icon="activity"
            indicator={highCriticalCount > 0 ? "coral" : "neutral"}
            onClick={() => navigate("#/incidents")}
          />
          <StatCard
            label="Available Resources"
            value={resources.error ? "—" : formatNumber(availableResources.length)}
            meta={`${formatNumber(totalAvailableUnits)} available units across ${formatNumber(
              resources.data.length
            )} pools`}
            icon="package"
            indicator="teal"
            onClick={() => navigate("#/resources")}
          />
          <StatCard
            label="Pending Review"
            value={formatNumber(pendingRecs.length)}
            meta={`${formatNumber(recommendations.length)} generated · ${formatNumber(
              actions.length
            )} decided`}
            icon="cpu"
            indicator={pendingRecs.length > 0 ? "amber" : "neutral"}
            onClick={() => navigate("#/recommendations")}
          />
        </section>
      )}

      {/* Primary Focus: Priority Incident Queue */}
      <PriorityQueueTable
        prioritySlice={priority}
        onRetry={refreshAll}
        onOpenCreateIncident={onOpenCreateIncident}
      />

      <AreaPriorityTable
        areaPrioritySlice={areaPriority}
        onRetry={refreshAll}
      />

      <WorkflowOverview
        incidentCount={incidents.data.length}
        prioritizedCount={openIncidents.length}
        recommendationCount={recommendations.length}
        decisionCount={actions.length}
      />

      <IncidentMapPanel incidents={openIncidents} resources={resources.data} />

      <DashboardLivePanels
        alerts={alerts.data}
        incidents={incidents.data}
        resources={resources.data}
        responsePlans={responsePlans.data}
        onRefresh={refreshAll}
      />
    </div>
  );
}
