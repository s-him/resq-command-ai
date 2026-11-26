import React, { useCallback, useEffect, useMemo, useState } from "react";
import { CodeBadge } from "../components/common/Badge";
import EmptyState from "../components/common/EmptyState";
import ErrorState from "../components/common/ErrorState";
import Icon from "../components/common/Icon";
import { SkeletonTable } from "../components/common/Skeleton";
import { useData } from "../context/DataContext";
import { navigate } from "../hooks/useHashRoute";
import { listActivity } from "../services/activityService";
import {
  dateKey,
  formatDateHeading,
  formatDateTime,
  incidentCode,
  labelize,
  recommendationCode,
  resourceCode,
} from "../utils/format";

const PAGE_LIMIT = 500;

const CATEGORIES = [
  { value: "all", label: "All event types", prefixes: [] },
  { value: "incident", label: "Incidents and status changes", prefixes: ["incident_"] },
  { value: "decision", label: "Recommendations and decisions", prefixes: ["recommendation_"] },
  { value: "plan", label: "Response plans and dispatch", prefixes: ["response_plan_", "dispatch_"] },
  { value: "resource", label: "Resource changes", prefixes: ["resource_"] },
  { value: "review", label: "External alert reviews", prefixes: ["external_alert_"] },
];

function iconFor(type) {
  if (type.startsWith("incident_")) return { icon: "alert", tone: "blue" };
  if (type.endsWith("_approved") || type.endsWith("_simulated")) return { icon: "checkCircle", tone: "teal" };
  if (type.endsWith("_rejected")) return { icon: "xCircle", tone: "slate" };
  if (type.startsWith("dispatch_")) return { icon: "ambulance", tone: "amber" };
  if (type.startsWith("resource_")) return { icon: "package", tone: "cyan" };
  return { icon: "cpu", tone: "cyan" };
}

export default function ActivityHistory() {
  const { lastUpdated, refreshing, refreshAll } = useData();
  const [log, setLog] = useState({ entries: [], total: 0, loading: true, error: null });
  const [category, setCategory] = useState("all");
  const [search, setSearch] = useState("");

  const load = useCallback(async () => {
    try {
      const result = await listActivity({ limit: PAGE_LIMIT });
      setLog({ entries: result.entries, total: result.total_count, loading: false, error: null });
    } catch (error) {
      setLog((current) => ({ ...current, loading: false, error }));
    }
  }, []);

  // lastUpdated changes whenever the shared data reloads (live stream or Refresh).
  useEffect(() => {
    load();
  }, [load, lastUpdated]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    const prefixes = CATEGORIES.find((item) => item.value === category)?.prefixes || [];
    return log.entries.filter((entry) => {
      if (prefixes.length && !prefixes.some((prefix) => entry.alert_type.startsWith(prefix))) return false;
      if (!q) return true;
      return [
        entry.message,
        entry.note,
        entry.actor,
        entry.incident_id ? incidentCode(entry.incident_id) : "",
        entry.recommendation_id ? recommendationCode(entry.recommendation_id) : "",
      ].some((value) => String(value || "").toLowerCase().includes(q));
    });
  }, [log.entries, category, search]);

  const groupedByDate = useMemo(() => {
    const groups = new Map();
    for (const entry of filtered) {
      const key = dateKey(entry.timestamp);
      if (!groups.has(key)) {
        groups.set(key, { key, heading: formatDateHeading(entry.timestamp), entries: [] });
      }
      groups.get(key).entries.push(entry);
    }
    return [...groups.values()];
  }, [filtered]);

  return (
    <div className="page-stack">
      <section className="page-hero">
        <div>
          <h2 className="page-heading">Activity &amp; Audit History</h2>
          <p className="page-subheading">
            The saved action log: incidents, status changes, notes, recommendations, decisions,
            response plans, simulated dispatch and resource changes.
          </p>
        </div>

        <div className="page-hero-actions">
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => {
              load();
              refreshAll();
            }}
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
              placeholder="Search by incident ID, recommendation ID, message, actor, or note..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              aria-label="Search activity history"
            />
          </div>

          <div className="filter-group">
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              aria-label="Filter by event category"
            >
              {CATEGORIES.map((item) => (
                <option key={item.value} value={item.value}>{item.label}</option>
              ))}
            </select>
          </div>
        </div>

        {log.total > log.entries.length && (
          <p className="field-hint">
            Showing the newest {log.entries.length} of {log.total} entries.
          </p>
        )}

        {log.error && log.entries.length === 0 ? (
          <ErrorState title="Could not load activity history" error={log.error} onRetry={load} />
        ) : log.loading ? (
          <SkeletonTable rows={5} />
        ) : log.entries.length === 0 ? (
          <EmptyState
            icon="history"
            title="No operational activity recorded yet"
            description="Actions appear here as soon as they are saved."
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
              setCategory("all");
            }}
          />
        ) : (
          <div className="date-groups-stack">
            {groupedByDate.map((group) => (
              <div key={group.key} className="date-group">
                <div className="date-group-heading">{group.heading}</div>
                <ol className="timeline-list">
                  {group.entries.map((entry) => {
                    const meta = iconFor(entry.alert_type);
                    return (
                      <li key={entry.log_id} className="timeline-item">
                        <span className={`timeline-dot timeline-dot-${meta.tone}`}>
                          <Icon name={meta.icon} size={14} />
                        </span>
                        <div className="timeline-card">
                          <div className="timeline-card-top">
                            <div className="timeline-title-row">
                              <strong>{labelize(entry.alert_type)}</strong>
                              {entry.incident_id && (
                                <CodeBadge onClick={() => navigate(`#/incidents/${entry.incident_id}`)}>
                                  {incidentCode(entry.incident_id)}
                                </CodeBadge>
                              )}
                              {entry.recommendation_id && (
                                <CodeBadge>{recommendationCode(entry.recommendation_id)}</CodeBadge>
                              )}
                              {entry.resource_id && <CodeBadge>{resourceCode(entry.resource_id)}</CodeBadge>}
                            </div>
                            <span className="text-muted tabular">
                              {formatDateTime(entry.timestamp)} · {entry.actor}
                            </span>
                          </div>
                          <p className="timeline-desc">{entry.message}</p>
                          {entry.note && (
                            <div className="timeline-note">
                              <strong>Note:</strong> {entry.note}
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
