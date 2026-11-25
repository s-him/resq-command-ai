import React, { useMemo, useState } from "react";
import { CodeBadge, SeverityBadge, StatusBadge } from "../components/common/Badge";
import EmptyState from "../components/common/EmptyState";
import ErrorState from "../components/common/ErrorState";
import Icon from "../components/common/Icon";
import { SkeletonTable } from "../components/common/Skeleton";
import { useData } from "../context/DataContext";
import { navigate } from "../hooks/useHashRoute";
import {
  HAZARD_ICONS,
  HAZARD_TYPES,
  INCIDENT_STATUSES,
  SEVERITY_LEVELS,
} from "../utils/constants";
import {
  formatDateTime,
  formatNumber,
  incidentCode,
  labelize,
} from "../utils/format";

export default function Incidents({ onOpenCreateIncident }) {
  const { incidents, priorityIndex, refreshing, refreshAll } = useData();

  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [hazardFilter, setHazardFilter] = useState("all");
  const [severityFilter, setSeverityFilter] = useState("all");
  const [sortBy, setSortBy] = useState("priority");

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    const list = incidents.data.filter((inc) => {
      if (statusFilter !== "all" && inc.status !== statusFilter) return false;
      if (hazardFilter !== "all" && inc.hazard_type !== hazardFilter) return false;
      if (severityFilter !== "all" && inc.severity?.level !== severityFilter) return false;
      if (!q) return true;
      return (
        incidentCode(inc.id).toLowerCase().includes(q) ||
        inc.hazard_type.toLowerCase().includes(q) ||
        inc.location.toLowerCase().includes(q) ||
        inc.description.toLowerCase().includes(q)
      );
    });

    return [...list].sort((a, b) => {
      if (sortBy === "priority") {
        const rankA = priorityIndex[a.id]?.priority?.rank ?? 999999;
        const rankB = priorityIndex[b.id]?.priority?.rank ?? 999999;
        if (rankA !== rankB) return rankA - rankB;
        return (b.severity?.score ?? 0) - (a.severity?.score ?? 0);
      }
      if (sortBy === "score") {
        return (b.severity?.score ?? 0) - (a.severity?.score ?? 0) || b.people_affected - a.people_affected;
      }
      if (sortBy === "people") {
        return b.people_affected - a.people_affected;
      }
      if (sortBy === "reported_desc") {
        return new Date(b.reported_at).getTime() - new Date(a.reported_at).getTime();
      }
      return b.id - a.id;
    });
  }, [incidents.data, priorityIndex, search, statusFilter, hazardFilter, severityFilter, sortBy]);

  return (
    <div className="page-stack">
      <section className="page-hero">
        <div>
          <h2 className="page-heading">Incident Management</h2>
          <p className="page-subheading">
            Search, filter, and sort all reported incidents, or open any record for severity
            analysis and resource recommendations.
          </p>
        </div>
        <div className="page-hero-actions">
          <button
            type="button"
            className="btn btn-secondary"
            onClick={refreshAll}
            disabled={refreshing}
          >
            <Icon name="refresh" size={16} className={refreshing ? "spin" : ""} />
            <span>Refresh</span>
          </button>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => onOpenCreateIncident()}
          >
            <Icon name="plus" size={16} />
            <span>Create Incident</span>
          </button>
        </div>
      </section>

      <section className="surface-card">
        <div className="toolbar-row">
          <div className="search-box">
            <Icon name="search" size={16} className="search-icon" />
            <input
              type="search"
              placeholder="Search incidents by ID, hazard, location, or description..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              aria-label="Search incidents"
            />
          </div>

          <div className="filter-group">
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              aria-label="Filter by incident status"
            >
              <option value="all">All statuses</option>
              {INCIDENT_STATUSES.map((st) => (
                <option key={st} value={st}>
                  {labelize(st)}
                </option>
              ))}
            </select>

            <select
              value={hazardFilter}
              onChange={(e) => setHazardFilter(e.target.value)}
              aria-label="Filter by hazard category"
            >
              <option value="all">All hazards</option>
              {HAZARD_TYPES.map((h) => (
                <option key={h} value={h}>
                  {labelize(h)}
                </option>
              ))}
            </select>

            <select
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value)}
              aria-label="Filter by severity level"
            >
              <option value="all">All severities</option>
              {SEVERITY_LEVELS.map((lvl) => (
                <option key={lvl} value={lvl}>
                  {lvl}
                </option>
              ))}
            </select>

            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              aria-label="Sort incidents"
            >
              <option value="priority">Sort: Priority Rank</option>
              <option value="score">Sort: Severity Score (High → Low)</option>
              <option value="people">Sort: People Affected (High → Low)</option>
              <option value="reported_desc">Sort: Reported Time (Newest)</option>
              <option value="id_desc">Sort: Incident ID (Newest)</option>
            </select>
          </div>
        </div>

        {incidents.error ? (
          <ErrorState
            title="Could not load incident records"
            error={incidents.error}
            onRetry={refreshAll}
          />
        ) : incidents.loading && incidents.data.length === 0 ? (
          <SkeletonTable rows={5} />
        ) : incidents.data.length === 0 ? (
          <EmptyState
            icon="alert"
            title="No reported incidents yet."
            description="Submit a manual or sample incident report to evaluate its severity score and generate resource recommendations."
            actionLabel="Create Demo Incident"
            onAction={() => onOpenCreateIncident("high")}
            secondaryActionLabel="Open Blank Form"
            onSecondaryAction={() => onOpenCreateIncident()}
          />
        ) : filtered.length === 0 ? (
          <EmptyState
            icon="search"
            title="No incidents match your filters"
            description="Reset the active search or dropdown filters to view all saved incidents."
            secondaryActionLabel="Reset Filters"
            onSecondaryAction={() => {
              setSearch("");
              setStatusFilter("all");
              setHazardFilter("all");
              setSeverityFilter("all");
            }}
          />
        ) : (
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Incident ID</th>
                  <th>Priority</th>
                  <th>Hazard Category</th>
                  <th>Location &amp; Help Needed</th>
                  <th>Reported Time</th>
                  <th>People Affected</th>
                  <th>Severity Level</th>
                  <th>Score</th>
                  <th>Status</th>
                  <th className="text-right">Action</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((inc) => {
                  const rank = priorityIndex[inc.id]?.priority?.rank;
                  return (
                    <tr
                      key={inc.id}
                      className="clickable-row"
                      onClick={() => navigate(`#/incidents/${inc.id}`)}
                    >
                      <td data-label="Incident ID">
                        <CodeBadge>{incidentCode(inc.id)}</CodeBadge>
                      </td>
                      <td data-label="Priority">
                        {rank ? (
                          <span className="rank-chip tabular">#{rank}</span>
                        ) : (
                          <span className="text-muted">—</span>
                        )}
                      </td>
                      <td data-label="Hazard Category">
                        <div className="cell-hazard">
                          <span className="hazard-icon-chip">
                            <Icon name={HAZARD_ICONS[inc.hazard_type] || "alert"} size={15} />
                          </span>
                          <span className="font-medium">{labelize(inc.hazard_type)}</span>
                        </div>
                      </td>
                      <td data-label="Location & Help">
                        <div className="cell-location">{inc.location}</div>
                        <div className="cell-sub">
                          Assistance: {inc.help_needed.map(labelize).join(", ")}
                        </div>
                      </td>
                      <td data-label="Reported Time" className="tabular text-muted">
                        {formatDateTime(inc.reported_at)}
                      </td>
                      <td data-label="People Affected" className="tabular font-medium">
                        {formatNumber(inc.people_affected)}
                      </td>
                      <td data-label="Severity Level">
                        <SeverityBadge level={inc.severity.level} />
                      </td>
                      <td data-label="Score">
                        <span className="score-pill tabular">
                          <strong>{inc.severity.score}</strong>/{inc.severity.max_score}
                        </span>
                      </td>
                      <td data-label="Status">
                        <StatusBadge status={inc.status} />
                      </td>
                      <td
                        data-label="Action"
                        className="text-right"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <button
                          type="button"
                          className="btn btn-secondary btn-xs"
                          onClick={() => navigate(`#/incidents/${inc.id}`)}
                        >
                          <span>Open Detail</span>
                          <Icon name="arrowRight" size={13} />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

