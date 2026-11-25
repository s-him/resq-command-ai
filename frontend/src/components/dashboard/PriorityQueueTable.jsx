import React, { useMemo, useState } from "react";
import { navigate } from "../../hooks/useHashRoute";
import {
  HAZARD_ICONS,
  HAZARD_TYPES,
  SEVERITY_LEVELS,
} from "../../utils/constants";
import {
  formatDateTime,
  formatNumber,
  incidentCode,
  labelize,
  priorityReason,
} from "../../utils/format";
import { CodeBadge, SeverityBadge, StatusBadge } from "../common/Badge";
import EmptyState from "../common/EmptyState";
import ErrorState from "../common/ErrorState";
import Icon from "../common/Icon";
import { SkeletonTable } from "../common/Skeleton";

const PAGE_SIZE = 8;

export default function PriorityQueueTable({
  prioritySlice,
  onRetry,
  onOpenCreateIncident,
}) {
  const [search, setSearch] = useState("");
  const [hazardFilter, setHazardFilter] = useState("all");
  const [severityFilter, setSeverityFilter] = useState("all");
  const [page, setPage] = useState(1);

  const incidents = prioritySlice.data?.incidents || [];
  const rankingRules = prioritySlice.data?.ranking_rules || [];

  // Keep exact backend priority ordering; only filter when the operator searches/filters.
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return incidents.filter((inc) => {
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
  }, [incidents, search, hazardFilter, severityFilter]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const safePage = Math.min(page, totalPages);
  const pageItems = filtered.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE);

  return (
    <section className="surface-card">
      <div className="panel-header">
        <div>
          <h2 className="section-title">Priority Incident Queue</h2>
          <p className="section-subtitle">
            Reported incidents ordered using the backend&apos;s prioritisation logic (severity score
            → people affected → earlier reported time → ID).
          </p>
        </div>
        {rankingRules.length > 0 && (
          <div className="rules-pill" title={rankingRules.join(" ")}>
            <Icon name="info" size={14} />
            <span>Backend tie-breaker rules active</span>
          </div>
        )}
      </div>

      {incidents.length > 0 && (
        <div className="toolbar-row">
          <div className="search-box">
            <Icon name="search" size={16} className="search-icon" />
            <input
              type="search"
              placeholder="Search by ID, hazard, location, or description..."
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              aria-label="Search priority incidents"
            />
          </div>

          <div className="filter-group">
            <select
              value={hazardFilter}
              onChange={(e) => {
                setHazardFilter(e.target.value);
                setPage(1);
              }}
              aria-label="Filter by hazard type"
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
              onChange={(e) => {
                setSeverityFilter(e.target.value);
                setPage(1);
              }}
              aria-label="Filter by severity level"
            >
              <option value="all">All severities</option>
              {SEVERITY_LEVELS.map((lvl) => (
                <option key={lvl} value={lvl}>
                  {lvl}
                </option>
              ))}
            </select>
          </div>
        </div>
      )}

      {prioritySlice.error ? (
        <ErrorState
          title="Could not load the priority incident queue"
          error={prioritySlice.error}
          onRetry={onRetry}
        />
      ) : prioritySlice.loading && incidents.length === 0 ? (
        <SkeletonTable rows={4} />
      ) : incidents.length === 0 ? (
        <EmptyState
          icon="alert"
          title="No reported incidents yet."
          description="Submit a manual or sample incident report to evaluate its rule-based severity score and priority position."
          actionLabel="Create Demo Incident"
          onAction={() => onOpenCreateIncident?.("high")}
          secondaryActionLabel="Open Blank Form"
          onSecondaryAction={() => onOpenCreateIncident?.()}
        />
      ) : filtered.length === 0 ? (
        <EmptyState
          icon="search"
          title="No incidents match the current filters"
          description="Try clearing the search query or selecting all hazards and severities."
          secondaryActionLabel="Reset Filters"
          onSecondaryAction={() => {
            setSearch("");
            setHazardFilter("all");
            setSeverityFilter("all");
          }}
        />
      ) : (
        <>
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Rank &amp; ID</th>
                  <th>Hazard</th>
                  <th>Location</th>
                  <th>Reported Time</th>
                  <th>People Affected</th>
                  <th>Severity</th>
                  <th>Score</th>
                  <th>Priority Explanation</th>
                  <th>Status</th>
                  <th className="text-right">Action</th>
                </tr>
              </thead>
              <tbody>
                {pageItems.map((inc) => (
                  <tr
                    key={inc.id}
                    className="clickable-row"
                    onClick={() => navigate(`#/incidents/${inc.id}`)}
                  >
                    <td data-label="Rank & ID">
                      <div className="cell-rank-id">
                        <span className="rank-chip tabular">#{inc.priority.rank}</span>
                        <CodeBadge>{incidentCode(inc.id)}</CodeBadge>
                      </div>
                    </td>
                    <td data-label="Hazard">
                      <div className="cell-hazard">
                        <span className="hazard-icon-chip">
                          <Icon name={HAZARD_ICONS[inc.hazard_type] || "alert"} size={15} />
                        </span>
                        <span className="font-medium">{labelize(inc.hazard_type)}</span>
                      </div>
                    </td>
                    <td data-label="Location">
                      <div className="cell-location">{inc.location}</div>
                      <div className="cell-sub">
                        Needs: {inc.help_needed.map(labelize).join(", ")}
                      </div>
                    </td>
                    <td data-label="Reported Time" className="tabular text-muted">
                      {formatDateTime(inc.reported_at)}
                    </td>
                    <td data-label="People Affected" className="tabular font-medium">
                      {formatNumber(inc.people_affected)}
                    </td>
                    <td data-label="Severity">
                      <SeverityBadge level={inc.severity.level} />
                    </td>
                    <td data-label="Score">
                      <span className="score-pill tabular">
                        <strong>{inc.severity.score}</strong>/{inc.severity.max_score}
                      </span>
                    </td>
                    <td data-label="Priority Explanation">
                      <div className="cell-explain" title={inc.priority.explanation}>
                        {priorityReason(inc.priority.explanation)}
                      </div>
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
                        <span>Investigate</span>
                        <Icon name="arrowRight" size={13} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {totalPages > 1 && (
            <div className="pagination-bar">
              <span className="text-muted tabular">
                Showing {(safePage - 1) * PAGE_SIZE + 1}–
                {Math.min(safePage * PAGE_SIZE, filtered.length)} of {filtered.length} open
                incidents
              </span>
              <div className="pagination-btns">
                <button
                  type="button"
                  className="btn btn-secondary btn-xs"
                  disabled={safePage <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  Previous
                </button>
                <span className="pagination-page tabular">
                  Page {safePage} of {totalPages}
                </span>
                <button
                  type="button"
                  className="btn btn-secondary btn-xs"
                  disabled={safePage >= totalPages}
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </section>
  );
}

