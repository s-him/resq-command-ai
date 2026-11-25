import React, { useCallback, useEffect, useState } from "react";
import { CodeBadge, SeverityBadge, StatusBadge } from "../components/common/Badge";
import ConfirmDialog from "../components/common/ConfirmDialog";
import EmptyState from "../components/common/EmptyState";
import ErrorState from "../components/common/ErrorState";
import Icon from "../components/common/Icon";
import { SkeletonTable } from "../components/common/Skeleton";
import SeverityPanel from "../components/incidents/SeverityPanel";
import { useData } from "../context/DataContext";
import { useToast } from "../context/ToastContext";
import { navigate } from "../hooks/useHashRoute";
import { describeError } from "../services/apiClient";
import { getIncident, getIncidentHistory } from "../services/incidentService";
import {
  generateRecommendation,
  submitDecision,
} from "../services/recommendationService";
import {
  HAZARD_ICONS,
  HUMAN_REVIEW_WARNING,
} from "../utils/constants";
import { buildActivityEvents, EVENT_META, EVENT_SOURCE_LABELS } from "../utils/events";
import {
  formatDateTime,
  formatNumber,
  incidentCode,
  labelize,
  recommendationCode,
  resourceCode,
} from "../utils/format";

export default function IncidentDetails({ incidentId }) {
  const { priorityIndex, lastUpdated, refreshAll, refreshIncidentHistory } = useData();
  const toast = useToast();

  const [incident, setIncident] = useState(null);
  const [history, setHistory] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [generating, setGenerating] = useState(false);
  const [notesByRec, setNotesByRec] = useState({});
  const [confirmState, setConfirmState] = useState(null);
  const [submittingDecision, setSubmittingDecision] = useState(false);

  const loadDetail = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [incData, histData] = await Promise.all([
        getIncident(incidentId),
        getIncidentHistory(incidentId),
      ]);
      setIncident(incData);
      setHistory(histData);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [incidentId]);

  // Reload whenever the route ID changes OR the user triggers a global Refresh in the topbar.
  useEffect(() => {
    loadDetail();
  }, [loadDetail, lastUpdated]);

  async function handleGenerateRecommendation() {
    if (generating || !incident) return;
    setGenerating(true);
    try {
      const rec = await generateRecommendation(incident.id);
      const updatedHist = await refreshIncidentHistory(incident.id);
      setHistory(updatedHist);
      toast({
        type: "success",
        title: `${recommendationCode(rec.id)} generated`,
        message: `${rec.items.length} resource match(es) · Pending Operator Review.`,
      });
    } catch (err) {
      toast({
        type: "error",
        title: "Could not generate recommendation",
        message: describeError(err),
      });
    } finally {
      setGenerating(false);
    }
  }

  async function handleConfirmDecision() {
    if (!confirmState || submittingDecision) return;
    const { rec, decision } = confirmState;
    const note = notesByRec[rec.id] || "";
    setSubmittingDecision(true);
    try {
      const result = await submitDecision(rec.id, decision, note);
      const updatedHist = await refreshIncidentHistory(incident.id);
      setHistory(updatedHist);
      await refreshAll();
      toast({
        type: "success",
        title: `${recommendationCode(rec.id)} ${decision}`,
        message: result.message,
      });
      setConfirmState(null);
    } catch (err) {
      toast({
        type: "error",
        title: "Decision could not be saved",
        message: describeError(err),
      });
    } finally {
      setSubmittingDecision(false);
    }
  }

  if (loading && !incident) {
    return (
      <div className="page-stack">
        <SkeletonTable rows={6} />
      </div>
    );
  }

  if (error || !incident) {
    return (
      <div className="page-stack">
        <div className="back-bar">
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() => navigate("#/incidents")}
          >
            <Icon name="chevronLeft" size={15} />
            <span>Back to Incidents</span>
          </button>
        </div>
        <ErrorState
          title={`Could not load incident #${incidentId}`}
          error={error}
          onRetry={loadDetail}
        />
      </div>
    );
  }

  const prioritized = priorityIndex[incident.id];
  const recommendations = [...(history?.recommendations || [])].reverse();
  const actions = history?.action_history || [];
  const timelineEvents = buildActivityEvents({
    incidents: [incident],
    recommendations: history?.recommendations || [],
    actions,
  });

  return (
    <div className="page-stack">
      <div className="back-bar">
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          onClick={() => navigate("#/incidents")}
        >
          <Icon name="chevronLeft" size={15} />
          <span>Back to Incidents</span>
        </button>
        <span className="meta-tag">Reported / Sample Incident Record</span>
      </div>

      {/* Header */}
      <section className="surface-card detail-header-card">
        <div className="detail-header-left">
          <div className="detail-id-row">
            <CodeBadge>{incidentCode(incident.id)}</CodeBadge>
            <StatusBadge status={incident.status} />
            <SeverityBadge
              level={incident.severity.level}
              score={incident.severity.score}
              maxScore={incident.severity.max_score}
              showScore
            />
          </div>
          <h2 className="detail-title">
            <Icon name={HAZARD_ICONS[incident.hazard_type] || "alert"} size={20} />
            <span>{labelize(incident.hazard_type)}</span>
            <span className="detail-location">· {incident.location}</span>
          </h2>
        </div>

        <div className="detail-header-actions">
          <button
            type="button"
            className="btn btn-secondary"
            onClick={loadDetail}
            disabled={loading}
          >
            <Icon name="refresh" size={15} />
            <span>Refresh</span>
          </button>
          <button
            type="button"
            className="btn btn-primary"
            onClick={handleGenerateRecommendation}
            disabled={generating}
          >
            <Icon name="cpu" size={15} />
            <span>
              {generating ? "Running matching rules..." : "Generate Resource Recommendation"}
            </span>
          </button>
        </div>
      </section>

      {/* Two-column: Incident Info + Priority Assessment */}
      <div className="detail-grid-2">
        <section className="surface-card">
          <h3 className="section-title">Incident Information</h3>
          <p className="detail-description">{incident.description}</p>

          <dl className="kv-grid">
            <div className="kv-item">
              <dt>Reported Time</dt>
              <dd className="tabular">{formatDateTime(incident.reported_at)}</dd>
            </div>
            <div className="kv-item">
              <dt>Recorded (UTC)</dt>
              <dd className="tabular">{formatDateTime(incident.created_at)}</dd>
            </div>
            <div className="kv-item">
              <dt>Estimated People Affected</dt>
              <dd className="tabular font-medium">
                {formatNumber(incident.people_affected)} people
              </dd>
            </div>
            <div className="kv-item">
              <dt>Coordinates (Reported / Sample)</dt>
              <dd className="tabular">
                {typeof incident.latitude === "number" && typeof incident.longitude === "number"
                  ? `${incident.latitude.toFixed(4)}, ${incident.longitude.toFixed(4)}`
                  : "Not supplied"}
              </dd>
            </div>
            <div className="kv-item kv-full">
              <dt>Requested Assistance</dt>
              <dd className="tag-row">
                {incident.help_needed.map((help) => (
                  <span key={help} className="assist-tag">
                    {labelize(help)}
                  </span>
                ))}
              </dd>
            </div>
          </dl>
        </section>

        <section className="surface-card">
          <h3 className="section-title">Priority Assessment</h3>
          <p className="section-subtitle">
            Current standing among open incidents using the backend&apos;s tie-breaker rules.
          </p>

          {prioritized ? (
            <div className="priority-box">
              <div className="priority-rank-display">
                <span className="priority-rank-label">Current Priority Rank</span>
                <span className="priority-rank-number tabular">
                  Rank #{prioritized.priority.rank}
                </span>
              </div>
              <div className="explain-callout">
                <strong>Ranking Explanation:</strong> {prioritized.priority.explanation}
              </div>
            </div>
          ) : (
            <div className="notice-box">
              <Icon name="info" size={16} />
              <div>
                <strong>Not in open priority queue</strong>
                <p>
                  Only open incidents appear in the priority queue (current status:{" "}
                  <strong>{labelize(incident.status)}</strong>).
                </p>
              </div>
            </div>
          )}
        </section>
      </div>

      {/* Severity Intelligence Panel */}
      <SeverityPanel severity={incident.severity} />

      {/* Resource Recommendation Engine & Operator Decision Centre */}
      <section className="surface-card">
        <div className="panel-header">
          <div>
            <h2 className="section-title">
              Resource Recommendations &amp; Operator Review
            </h2>
            <p className="section-subtitle">
              Compares requested assistance against available resource inventory. Generating or
              approving a recommendation does not deduct stock.
            </p>
          </div>
          <button
            type="button"
            className="btn btn-primary btn-sm"
            onClick={handleGenerateRecommendation}
            disabled={generating}
          >
            <Icon name="cpu" size={15} />
            <span>
              {generating ? "Generating..." : "Generate Resource Recommendation"}
            </span>
          </button>
        </div>

        <div className="review-banner">
          <Icon name="shield" size={16} />
          <span>{HUMAN_REVIEW_WARNING}</span>
        </div>

        {recommendations.length === 0 ? (
          <EmptyState
            icon="cpu"
            title="No resource recommendations generated for this incident yet"
            description="Run the recommendation engine to match this incident's requested assistance against registered available resources."
            actionLabel="Generate Resource Recommendation"
            onAction={handleGenerateRecommendation}
            secondaryActionLabel="View Resource Inventory"
            onSecondaryAction={() => navigate("#/resources")}
          />
        ) : (
          <div className="rec-stack">
            {recommendations.map((rec) => {
              const isPending = rec.status === "pending";
              return (
                <article key={rec.id} className="rec-panel">
                  <div className="rec-panel-header">
                    <div className="rec-panel-title-row">
                      <CodeBadge>{recommendationCode(rec.id)}</CodeBadge>
                      <StatusBadge status={rec.status} />
                      {isPending && (
                        <span className="pending-review-tag">Pending Operator Review</span>
                      )}
                    </div>
                    <span className="text-muted tabular">
                      Generated {formatDateTime(rec.created_at)}
                    </span>
                  </div>

                  <p className="rec-summary-line">{rec.summary}</p>

                  {/* Visual Resource Matching Table */}
                  <div className="rec-section">
                    <div className="rec-subhead-row">
                      <h4 className="rec-subhead">Resource Matching Comparison</h4>
                      {rec.unavailable_needs.length > 0 && (
                        <button
                          type="button"
                          className="btn btn-secondary btn-xs"
                          onClick={() => navigate("#/resources")}
                        >
                          <span>Register Missing Resources in Inventory</span>
                          <Icon name="arrowRight" size={12} />
                        </button>
                      )}
                    </div>

                    <div className="table-scroll">
                      <table className="data-table compact-table">
                        <thead>
                          <tr>
                            <th>Requested Help</th>
                            <th>Recommended Resource</th>
                            <th>Location</th>
                            <th>Quantity (Suggested / Available)</th>
                            <th>Distance (Straight-line)</th>
                            <th>Status</th>
                          </tr>
                        </thead>
                        <tbody>
                          {rec.items.map((item) => {
                            const hasShortfall = (rec.insufficient_needs || []).some(
                              (s) => s.resource_type === item.resource_type
                            );
                            return (
                              <tr key={`${rec.id}-item-${item.resource_id}`}>
                                <td data-label="Requested Help">
                                  {(item.for_help_needed || []).map(labelize).join(", ")}
                                </td>
                                <td data-label="Recommended Resource">
                                  <div className="font-medium">
                                    {item.resource_name}{" "}
                                    <CodeBadge>{resourceCode(item.resource_id)}</CodeBadge>
                                  </div>
                                  <div className="cell-sub">{labelize(item.resource_type)}</div>
                                </td>
                                <td data-label="Location">{item.resource_location}</td>
                                <td
                                  data-label="Suggested / Available"
                                  className="tabular font-medium"
                                >
                                  {formatNumber(item.recommended_quantity)} /{" "}
                                  {formatNumber(item.available_quantity)} units
                                </td>
                                <td data-label="Distance (Straight-line)" className="tabular">
                                  {typeof item.distance_km === "number"
                                    ? `${item.distance_km.toFixed(2)} km`
                                    : "Not calculated"}
                                </td>
                                <td data-label="Status">
                                  <StatusBadge status={hasShortfall ? "limited" : "available"} />
                                </td>
                              </tr>
                            );
                          })}
                          {rec.unavailable_needs.map((gap, idx) => (
                            <tr key={`${rec.id}-unavail-${idx}`} className="row-shortage">
                              <td data-label="Requested Help">
                                {(gap.help_needed || []).map(labelize).join(", ")}
                              </td>
                              <td data-label="Recommended Resource">
                                <span className="font-medium">
                                  No available {labelize(gap.resource_type)}
                                </span>
                              </td>
                              <td data-label="Location" className="text-muted">
                                —
                              </td>
                              <td
                                data-label="Suggested / Available"
                                className="tabular text-danger"
                              >
                                0 available units
                              </td>
                              <td data-label="Distance (Straight-line)" className="text-muted">—</td>
                              <td data-label="Status">
                                <StatusBadge status="unavailable" />
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>

                  {/* Why This Recommendation? */}
                  <div className="rec-section">
                    <h4 className="rec-subhead">Why This Recommendation?</h4>
                    <div className="why-list">
                      {rec.items.map((item) => (
                        <div key={`why-${rec.id}-${item.resource_id}`} className="why-item why-item-match">
                          <div className="why-item-head">
                            <Icon name="checkCircle" size={14} />
                            <strong>Matched · {item.resource_name}</strong>
                          </div>
                          <p>{item.explanation}</p>
                        </div>
                      ))}

                      {(rec.insufficient_needs || []).map((shortfall, idx) => (
                        <div
                          key={`short-${rec.id}-${idx}`}
                          className="why-item why-item-warn"
                        >
                          <div className="why-item-head">
                            <Icon name="alert" size={14} />
                            <strong>
                              Partial Shortfall · {labelize(shortfall.resource_type)}
                            </strong>
                          </div>
                          <p>{shortfall.message}</p>
                        </div>
                      ))}

                      {rec.unavailable_needs.map((gap, idx) => (
                        <div
                          key={`gap-${rec.id}-${idx}`}
                          className="why-item why-item-danger"
                        >
                          <div className="why-item-head">
                            <Icon name="xCircle" size={14} />
                            <strong>
                              Unfulfilled Requirement · {labelize(gap.resource_type)}
                            </strong>
                          </div>
                          <p>{gap.message}</p>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Operator Decision Centre */}
                  {isPending ? (
                    <div className="decision-box">
                      <div className="decision-box-head">
                        <strong>Operator Decision</strong>
                        <span className="text-muted">
                          Records an audit decision in SQLite without dispatching or deducting
                          resources.
                        </span>
                      </div>
                      <div className="form-field">
                        <label htmlFor={`op-note-${rec.id}`}>
                          Decision Note (optional, max 300 characters)
                        </label>
                        <textarea
                          id={`op-note-${rec.id}`}
                          rows={2}
                          maxLength={300}
                          placeholder="Add an explanation for this operator decision..."
                          value={notesByRec[rec.id] || ""}
                          onChange={(e) =>
                            setNotesByRec((prev) => ({ ...prev, [rec.id]: e.target.value }))
                          }
                        />
                      </div>
                      <div className="decision-actions">
                        <button
                          type="button"
                          className="btn btn-teal"
                          onClick={() =>
                            setConfirmState({ rec, decision: "approved" })
                          }
                        >
                          <Icon name="checkCircle" size={15} />
                          <span>Approve Recommendation</span>
                        </button>
                        <button
                          type="button"
                          className="btn btn-danger-outline"
                          onClick={() =>
                            setConfirmState({ rec, decision: "rejected" })
                          }
                        >
                          <Icon name="xCircle" size={15} />
                          <span>Reject Recommendation</span>
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="recorded-decision-box">
                      <div className="recorded-decision-top">
                        <strong>Recorded Operator Decision:</strong>
                        <StatusBadge status={rec.status} />
                        <span className="text-muted tabular">
                          Decided {formatDateTime(rec.decided_at)}
                        </span>
                      </div>
                      <p className="recorded-decision-note">
                        <strong>Operator Note:</strong>{" "}
                        {rec.decision_note || "No note entered."}
                      </p>
                    </div>
                  )}

                  {rec.disclaimer && (
                    <div className="prototype-footnote">
                      <Icon name="info" size={13} />
                      <span>{rec.disclaimer}</span>
                    </div>
                  )}
                </article>
              );
            })}
          </div>
        )}
      </section>

      {/* Related Activity History */}
      <section className="surface-card">
        <div className="panel-header">
          <div>
            <h2 className="section-title">Incident Activity &amp; Audit Log</h2>
            <p className="section-subtitle">
              Chronological events recorded for {incidentCode(incident.id)}.
            </p>
          </div>
        </div>

        {timelineEvents.length === 0 ? (
          <EmptyState
            icon="history"
            title="No activity recorded yet"
            description="Events appear here as recommendations are generated and reviewed."
          />
        ) : (
          <ol className="timeline-list">
            {timelineEvents.map((ev) => {
              const meta = EVENT_META[ev.type] || EVENT_META.incident_reported;
              return (
                <li key={ev.key} className="timeline-item">
                  <span className={`timeline-dot timeline-dot-${meta.tone}`}>
                    <Icon name={meta.icon} size={13} />
                  </span>
                  <div className="timeline-card">
                    <div className="timeline-card-top">
                      <div className="timeline-title-row">
                        <strong>{meta.label}</strong>
                        {ev.recommendationId && (
                          <CodeBadge>{recommendationCode(ev.recommendationId)}</CodeBadge>
                        )}
                        {ev.decision && <StatusBadge status={ev.decision} />}
                      </div>
                      <span className="text-muted tabular">
                        {formatDateTime(ev.timestamp)} · {EVENT_SOURCE_LABELS[ev.source]}
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
        )}
      </section>

      <ConfirmDialog
        open={Boolean(confirmState)}
        decision={confirmState?.decision}
        recommendation={confirmState?.rec}
        note={confirmState ? notesByRec[confirmState.rec.id] : ""}
        submitting={submittingDecision}
        onCancel={() => setConfirmState(null)}
        onConfirm={handleConfirmDecision}
      />
    </div>
  );
}
