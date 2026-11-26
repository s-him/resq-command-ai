import React from "react";
import { navigate } from "../../hooks/useHashRoute";
import { labelize } from "../../utils/format";

const VISIBLE_LIMIT = 4;

/** Alerts the prototype raises about its own incidents, approvals and shortfalls. */
export default function ActiveAlertsPanel({ alerts = [] }) {
  const visible = alerts.slice(0, VISIBLE_LIMIT);
  return (
    <section className="surface-card live-panel">
      <div className="panel-header">
        <div>
          <h2 className="section-title">Active Alerts</h2>
          <p className="section-subtitle">High-severity incidents, pending approvals and resource shortfalls.</p>
        </div>
        <span className="live-count">{alerts.length} active</span>
      </div>
      {visible.length === 0 ? (
        <div className="live-empty">No active alerts.</div>
      ) : (
        <div className="live-alert-list">
          {visible.map((alert, index) => (
            <article className="live-alert-row" key={`${alert.alert_type}-${alert.incident_id}-${index}`}>
              <div className="live-alert-heading">
                <strong>{labelize(alert.alert_type)}</strong>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => navigate(`#/incidents/${alert.incident_id}`)}
                >
                  Open
                </button>
              </div>
              <div className="live-alert-meta">
                <span>{alert.message}</span>
              </div>
            </article>
          ))}
        </div>
      )}
      {alerts.length > visible.length && (
        <p className="live-panel-footnote">Showing {visible.length} of {alerts.length} alerts.</p>
      )}
    </section>
  );
}
