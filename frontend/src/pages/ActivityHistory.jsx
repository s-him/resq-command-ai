import React, { useMemo, useState } from "react";
import { CodeBadge, StatusBadge } from "../components/common/Badge";
import EmptyState from "../components/common/EmptyState";
import ErrorState from "../components/common/ErrorState";
import Icon from "../components/common/Icon";
import { SkeletonTable } from "../components/common/Skeleton";
import { useData } from "../context/DataContext";
import { navigate } from "../hooks/useHashRoute";
import {
  buildActivityEvents,
  EVENT_META,
  EVENT_SOURCE_LABELS,
} from "../utils/events";
import {
  dateKey,
  formatDateHeading,
  formatDateTime,
  incidentCode,
  recommendationCode,
} from "../utils/format";

export default function ActivityHistory() {
  const {
    incidents,
    recommendations,
    actions,
    histories,
    refreshing,
    refreshAll,
  } = useData();

  const [typeFilter, setTypeFilter] = useState("all");
  const [search, setSearch] = useState("");

  const allEvents = useMemo(
    () =>
      buildActivityEvents({
        incidents: incidents.data,
        recommendations,
        actions,
      }),
    [incidents.data, recommendations, actions]
  );

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return allEvents.filter((ev) => {
      if (typeFilter !== "all" && ev.type !== typeFilter) return false;
      if (!q) return true;
      return (
        incidentCode(ev.incidentId).toLowerCase().includes(q) ||
        (ev.recommendationId &&
          recommendationCode(ev.recommendationId).toLowerCase().includes(q)) ||
        ev.description.toLowerCase().includes(q) ||
        (ev.note || "").toLowerCase().includes(q)
      );
    });
  }, [allEvents, typeFilter, search]);

  const groupedByDate = useMemo(() => {
    const groups = [];
    const indexByKey = {};
    for (const ev of filtered) {
      const key = dateKey(ev.timestamp);
      if (!(key in indexByKey)) {
        indexByKey[key] = groups.length;
        groups.push({
          key,
          heading: formatDateHeading(ev.timestamp),
          events: [],
        });
      }
      groups[indexByKey[key]].events.push(ev);
    }
    return groups;
  }, [filtered]);

  return (
    <div className="page-stack">
      <section className="page-hero">
        <div>
          <h2 className="page-heading">Activity &amp; Audit History</h2>
          <p className="page-subheading">
            Chronological operational audit trail of reported incidents, generated recommendations,
            and recorded operator decisions.
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
        </div>
      </section>

      <section className="surface-card">
        <div className="toolbar-row">
          <div className="search-box">
            <Icon name="search" size={16} className="search-icon" />
            <input
              type="search"
              placeholder="Search audit events by incident ID, recommendation ID, description, or operator note..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              aria-label="Search activity history"
            />
          </div>

          <div className="filter-group">
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              aria-label="Filter by event category"
            >
              <option value="all">All event types</option>
              <option value="recommendation_approved">Operator Approvals</option>
              <option value="recommendation_rejected">Operator Rejections</option>
              <option value="recommendation_generated">Recommendations Generated</option>
              <option value="incident_reported">Incidents Reported</option>
            </select>
          </div>
        </div>

        {histories.error && allEvents.length === 0 ? (
          <ErrorState
            title="Could not load activity history"
            error={histories.error}
            onRetry={refreshAll}
          />
        ) : histories.loading && allEvents.length === 0 ? (
          <SkeletonTable rows={5} />
        ) : allEvents.length === 0 ? (
          <EmptyState
            icon="history"
            title="No operational activity recorded yet"
            description="As incidents are reported, recommendations are generated, and operator decisions are saved, their chronological audit trail appears here."
            actionLabel="Return to Dashboard"
            onAction={() => navigate("#/")}
          />
        ) : filtered.length === 0 ? (
          <EmptyState
            icon="search"
            title="No audit events match your filter"
            description="Clear the search box or select all event types."
            secondaryActionLabel="Reset Filters"
            onSecondaryAction={() => {
              setSearch("");
              setTypeFilter("all");
            }}
          />
        ) : (
          <div className="date-groups-stack">
            {groupedByDate.map((group) => (
              <div key={group.key} className="date-group">
                <div className="date-group-heading">{group.heading}</div>
                <ol className="timeline-list">
                  {group.events.map((ev) => {
                    const meta = EVENT_META[ev.type] || EVENT_META.incident_reported;
                    return (
                      <li key={ev.key} className="timeline-item">
                        <span className={`timeline-dot timeline-dot-${meta.tone}`}>
                          <Icon name={meta.icon} size={14} />
                        </span>
                        <div className="timeline-card">
                          <div className="timeline-card-top">
                            <div className="timeline-title-row">
                              <strong>{meta.label}</strong>
                              <CodeBadge
                                onClick={() => navigate(`#/incidents/${ev.incidentId}`)}
                              >
                                {incidentCode(ev.incidentId)}
                              </CodeBadge>
                              {ev.recommendationId && (
                                <CodeBadge>
                                  {recommendationCode(ev.recommendationId)}
                                </CodeBadge>
                              )}
                              {ev.decision && <StatusBadge status={ev.decision} />}
                            </div>
                            <span className="text-muted tabular">
                              {formatDateTime(ev.timestamp)} ·{" "}
                              {EVENT_SOURCE_LABELS[ev.source]}
                            </span>
                          </div>
                          <p className="timeline-desc">{ev.description}</p>
                          {ev.note && (
                            <div className="timeline-note">
                              <strong>Operator Note:</strong> {ev.note}
                            </div>
                          )}
                        </div>
                      </li>
                    );
                  })}
                </ol>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

