import React from "react";
import { navigate } from "../../hooks/useHashRoute";
import { formatDateTime, formatNumber, incidentCode } from "../../utils/format";
import { CodeBadge, SeverityBadge } from "../common/Badge";
import EmptyState from "../common/EmptyState";
import ErrorState from "../common/ErrorState";
import Icon from "../common/Icon";
import { SkeletonTable } from "../common/Skeleton";

/**
 * Area-level aggregate built only from the location strings already recorded
 * on open incidents. It is not a geographic boundary or population estimate.
 */
export default function AreaPriorityTable({ areaPrioritySlice, onRetry }) {
  const areas = areaPrioritySlice.data?.areas || [];
  const rules = areaPrioritySlice.data?.ranking_rules || [];

  return (
    <section className="surface-card">
      <div className="panel-header">
        <div>
          <h2 className="section-title">Affected-Area Priority</h2>
          <p className="section-subtitle">
            Open incidents grouped by their reported location, ranked by highest incident
            severity and total people affected.
          </p>
        </div>
        {rules.length > 0 && (
          <span className="rules-pill" title={rules.join(" ")}>
            <Icon name="mapPin" size={14} />
            <span>Area ranking active</span>
          </span>
        )}
      </div>

      <p className="area-priority-note">
        Location labels are grouped by trimmed, case-insensitive text only. No boundaries
        or population exposure are inferred.
      </p>

      {areaPrioritySlice.error ? (
        <ErrorState
          title="Could not load affected-area priority"
          error={areaPrioritySlice.error}
          onRetry={onRetry}
        />
      ) : areaPrioritySlice.loading && areas.length === 0 ? (
        <SkeletonTable rows={3} />
      ) : areas.length === 0 ? (
        <EmptyState
          icon="map-pin"
          title="No open areas to rank"
          description="Open incidents will be grouped here by their reported location."
        />
      ) : (
        <div className="table-scroll">
          <table className="data-table area-priority-table">
            <thead>
              <tr>
                <th>Area Rank</th>
                <th>Reported Area</th>
                <th>Open Incidents</th>
                <th>People Affected (reported)</th>
                <th>Top Severity</th>
                <th>Top Incident</th>
                <th>First Reported</th>
              </tr>
            </thead>
            <tbody>
              {areas.map((area) => (
                <tr
                  key={area.area.toLowerCase()}
                  className="clickable-row"
                  onClick={() => navigate(`#/incidents/${area.top_incident_id}`)}
                  title={area.explanation}
                >
                  <td data-label="Area Rank">
                    <span className="rank-chip tabular">#{area.rank}</span>
                  </td>
                  <td data-label="Reported Area">
                    <strong>{area.area}</strong>
                  </td>
                  <td data-label="Open Incidents" className="tabular">
                    {formatNumber(area.incident_count)}
                  </td>
                  <td data-label="People Affected (reported)" className="tabular font-medium">
                    {formatNumber(area.people_affected_reported)}
                  </td>
                  <td data-label="Top Severity">
                    <SeverityBadge level={area.highest_severity_level} />
                    <div className="cell-sub tabular">
                      {area.highest_severity_score}/100
                    </div>
                  </td>
                  <td data-label="Top Incident">
                    <CodeBadge>{incidentCode(area.top_incident_id)}</CodeBadge>
                  </td>
                  <td data-label="First Reported" className="tabular text-muted">
                    {formatDateTime(area.earliest_reported_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
