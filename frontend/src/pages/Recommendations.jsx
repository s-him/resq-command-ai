import React, { useMemo, useState } from "react";
import { CodeBadge, SeverityBadge, StatusBadge } from "../components/common/Badge";
import ConfirmDialog from "../components/common/ConfirmDialog";
import EmptyState from "../components/common/EmptyState";
import ErrorState from "../components/common/ErrorState";
import Icon from "../components/common/Icon";
import { SkeletonTable } from "../components/common/Skeleton";
import { useData } from "../context/DataContext";
import { useToast } from "../context/ToastContext";
import { navigate } from "../hooks/useHashRoute";
import { describeError } from "../services/apiClient";
import {
  generateRecommendation,
  getRecommendation,
  submitDecision,
} from "../services/recommendationService";
import {
  HUMAN_REVIEW_WARNING,
  RECOMMENDATION_STATUSES,
} from "../utils/constants";
import {
  formatDateTime,
  formatNumber,
  incidentCode,
  labelize,
  recommendationCode,
  resourceCode,
} from "../utils/format";

export default function Recommendations() {
  const {
    incidents,
    incidentIndex,
    priorityIndex,
    recommendations,
    histories,
    refreshing,
    refreshAll,
    refreshIncidentHistory,
  } = useData();
  const toast = useToast();

  const [statusFilter, setStatusFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [selectedIncidentForGen, setSelectedIncidentForGen] = useState("");
  const [generating, setGenerating] = useState(false);

  const [notesByRec, setNotesByRec] = useState({});
  const [confirmState, setConfirmState] = useState(null);
  const [submittingDecision, setSubmittingDecision] = useState(false);

  const [lookupId, setLookupId] = useState("");
  const [lookupLoading, setLookupLoading] = useState(false);
  const [lookupResult, setLookupResult] = useState(null);
  const [lookupError, setLookupError] = useState(null);

  // Order incident selector by priority rank first so the most urgent incident is default.
  const orderedIncidents = useMemo(() => {
    return [...incidents.data].sort((a, b) => {
      const rA = priorityIndex[a.id]?.priority?.rank ?? 999999;
      const rB = priorityIndex[b.id]?.priority?.rank ?? 999999;
      return rA - rB || b.id - a.id;
    });
  }, [incidents.data, priorityIndex]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return recommendations.filter((rec) => {
      if (statusFilter !== "all" && rec.status !== statusFilter) return false;
      if (!q) return true;
      const inc = incidentIndex[rec.incident_id];
      return (
        recommendationCode(rec.id).toLowerCase().includes(q) ||
        incidentCode(rec.incident_id).toLowerCase().includes(q) ||
        (inc?.location || "").toLowerCase().includes(q) ||
        rec.summary.toLowerCase().includes(q)
      );
    });
  }, [recommendations, incidentIndex, statusFilter, search]);

  async function handleLookupById(event) {
    event.preventDefault();
    const id = Number(lookupId);
    if (!Number.isInteger(id) || id <= 0) {
      setLookupError(new Error("Enter a positive whole recommendation ID (e.g. 1)."));
      setLookupResult(null);
      return;
    }
    setLookupLoading(true);
    setLookupError(null);
    try {
      const rec = await getRecommendation(id);
      setLookupResult(rec);
    } catch (err) {
      setLookupResult(null);
      setLookupError(err);
    } finally {
      setLookupLoading(false);
    }
  }

  async function handleGenerateForSelected() {
    const targetId = Number(selectedIncidentForGen || orderedIncidents[0]?.id);
    if (!targetId || generating) return;
    setGenerating(true);
    try {
      const created = await generateRecommendation(targetId);
      await refreshIncidentHistory(targetId);
      toast({
        type: "success",
        title: `${recommendationCode(created.id)} generated`,
        message: `Linked to ${incidentCode(targetId)} · Pending Operator Review.`,
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
      await refreshIncidentHistory(rec.incident_id);
      await refreshAll();
      if (lookupResult?.id === rec.id) {
        setLookupResult(result.recommendation);
      }
      toast({
        type: "success",
        title: `${recommendationCode(rec.id)} ${decision}`,
        message: result.message,
      });
      setConfirmState(null);
    } catch (err) {
      toast({
        type: "error",
        title: "Could not record operator decision",
        message: describeError(err),
      });
    } finally {
      setSubmittingDecision(false);
    }
  }

  return (
    <div className="page-stack">
      <section className="page-hero">
        <div>
          <h2 className="page-heading">
            Resource Recommendations &amp; Operator Decision Centre
          </h2>
          <p className="page-subheading">
            Review prototype resource suggestions generated across incidents and record human
            operator approvals or rejections.
          </p>
        </div>

        <div className="page-hero-actions">
          {orderedIncidents.length > 0 && (
            <div className="quick-gen-bar">
              <select
                value={selectedIncidentForGen || orderedIncidents[0]?.id || ""}
                onChange={(e) => setSelectedIncidentForGen(e.target.value)}
                aria-label="Select incident for recommendation generation"
              >
                {orderedIncidents.map((inc) => {
                  const rank = priorityIndex[inc.id]?.priority?.rank;
                  return (
                    <option key={inc.id} value={inc.id}>
                      {rank ? `#${rank} ` : ""}
                      {incidentCode(inc.id)} · {labelize(inc.hazard_type)} ({inc.location})
                    </option>
                  );
                })}
              </select>
              <button
                type="button"
                className="btn btn-primary"
                onClick={handleGenerateForSelected}
                disabled={generating}
              >
                <Icon name="cpu" size={15} />
                <span>{generating ? "Generating..." : "Generate Recommendation"}</span>
              </button>
            </div>
          )}
          <button
            type="button"
            className="btn btn-secondary"
            onClick={refreshAll}
            disabled={refreshing}
          >
            <Icon name="refresh" size={15} className={refreshing ? "spin" : ""} />
            <span>Refresh</span>
          </button>
        </div>
      </section>

      <div className="review-banner">
        <Icon name="shield" size={16} />
        <span>{HUMAN_REVIEW_WARNING}</span>
      </div>

      {/* Direct recommendation lookup by ID */}
      <section className="surface-card">
        <div
          className="toolbar-row"
          style={{ marginBottom: lookupResult || lookupError ? 12 : 0 }}
        >
          <div>
            <h3 className="section-title">Lookup Recommendation by ID</h3>
            <p className="section-subtitle">
              Find a specific recommendation by its numeric identifier.
            </p>
          </div>
          <form onSubmit={handleLookupById} className="quick-gen-bar">
            <input
              type="number"
              min="1"
              step="1"
              placeholder="Recommendation ID (e.g. 1)"
              value={lookupId}
              onChange={(e) => setLookupId(e.target.value)}
              aria-label="Recommendation ID to look up"
              className="lookup-input"
            />
            <button
              type="submit"
              className="btn btn-secondary btn-sm"
              disabled={lookupLoading}
            >
              <Icon name="search" size={14} />
              <span>{lookupLoading ? "Looking up..." : "Fetch by ID"}</span>
            </button>
            {(lookupResult || lookupError) && (
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => {
                  setLookupId("");
                  setLookupResult(null);
                  setLookupError(null);
                }}
              >
                Clear
              </button>
            )}
          </form>
        </div>

        {lookupError && (
          <ErrorState title="Recommendation lookup failed" error={lookupError} />
        )}

        {lookupResult && (
          <div className="explain-callout">
            <div className="rec-panel-header">
              <div className="rec-panel-title-row">
                <CodeBadge>{recommendationCode(lookupResult.id)}</CodeBadge>
                <StatusBadge status={lookupResult.status} />
                <span>for</span>
                <CodeBadge
                  onClick={() => navigate(`#/incidents/${lookupResult.incident_id}`)}
                >
                  {incidentCode(lookupResult.incident_id)}
                </CodeBadge>
              </div>
              <span className="text-muted tabular">
                Created {formatDateTime(lookupResult.created_at)}
              </span>
            </div>
            <p style={{ margin: "6px 0 0" }}>{lookupResult.summary}</p>
            {lookupResult.decision_note && (
              <p style={{ margin: "4px 0 0" }}>
                <strong>Operator Note:</strong> {lookupResult.decision_note}
              </p>
            )}
          </div>
        )}
      </section>

      <section className="surface-card">
        <div className="toolbar-row">
          <div className="search-box">
            <Icon name="search" size={15} className="search-icon" />
            <input
              type="search"
              placeholder="Search by recommendation ID, incident ID, location, or summary..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              aria-label="Search recommendations"
            />
          </div>

          <div className="filter-group">
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              aria-label="Filter by recommendation status"
            >
              <option value="all">All review states</option>
              {RECOMMENDATION_STATUSES.map((st) => (
                <option key={st} value={st}>
                  {labelize(st)}
                </option>
              ))}
            </select>
          </div>
        </div>

        {histories.error && recommendations.length === 0 ? (
          <ErrorState
            title="Could not load recommendations"
            error={histories.error}
            onRetry={refreshAll}
          />
        ) : histories.loading && recommendations.length === 0 ? (
          <SkeletonTable rows={4} />
        ) : recommendations.length === 0 ? (
          <EmptyState
            icon="cpu"
            title="No resource recommendations generated yet"
            description={
              orderedIncidents.length > 0
                ? "Select an incident above and click 'Generate Recommendation' to run the matching engine."
                : "Report an incident and register resources first, then generate a recommendation for operator review."
            }
            actionLabel={
              orderedIncidents.length > 0 ? "Generate Recommendation Now" : "Go to Incidents"
            }
            onAction={
              orderedIncidents.length > 0
                ? handleGenerateForSelected
                : () => navigate("#/incidents")
            }
          />
        ) : filtered.length === 0 ? (
          <EmptyState
            icon="search"
            title="No recommendations match your filters"
            description="Reset the search query or review-status filter."
            secondaryActionLabel="Reset Filters"
            onSecondaryAction={() => {
              setSearch("");
              setStatusFilter("all");
            }}
          />
        ) : (
          <div className="rec-stack">
            {filtered.map((rec) => {
              const inc = incidentIndex[rec.incident_id];
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
                      {inc && (
                        <>
                          <span className="text-muted">for</span>
                          <CodeBadge onClick={() => navigate(`#/incidents/${inc.id}`)}>
                            {incidentCode(inc.id)} · {labelize(inc.hazard_type)}
                          </CodeBadge>
                          <SeverityBadge level={inc.severity.level} />
                        </>
                      )}
                    </div>
                    <div className="rec-panel-meta">
                      <span className="text-muted tabular">
                        Generated {formatDateTime(rec.created_at)}
                      </span>
                      <button
                        type="button"
                        className="btn btn-secondary btn-xs"
                        onClick={() => navigate(`#/incidents/${rec.incident_id}`)}
                      >
                        <span>Open Incident</span>
                        <Icon name="arrowRight" size={12} />
                      </button>
                    </div>
                  </div>

                  <p className="rec-summary-line">{rec.summary}</p>

                  {/* Unified Resource Matching Table (shows matched items AND unavailable gaps) */}
                  <div className="rec-section">
                    <div className="rec-subhead-row">
                      <h4 className="rec-subhead">Resource Matching Comparison</h4>
                      {rec.unavailable_needs.length > 0 && (
                        <button
                          type="button"
                          className="btn btn-secondary btn-xs"
                          onClick={() => navigate("#/resources")}
                        >
                          <span>Register Missing Resources</span>
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
                            <th>Status</th>
                          </tr>
                        </thead>
                        <tbody>
                          {rec.items.map((item) => {
                            const hasShortfall = (rec.insufficient_needs || []).some(
                              (s) => s.resource_type === item.resource_type
                            );
                            return (
                              <tr key={`${rec.id}-${item.resource_id}`}>
                                <td data-label="Requested Help">
                                  {(item.for_help_needed || []).map(labelize).join(", ")}
                                </td>
                                <td data-label="Recommended Resource">
                                  <strong>{item.resource_name}</strong>{" "}
                                  <CodeBadge>{resourceCode(item.resource_id)}</CodeBadge>
                                </td>
                                <td data-label="Location">{item.resource_location}</td>
                                <td
                                  data-label="Suggested / Available"
                                  className="tabular font-medium"
                                >
                                  {formatNumber(item.recommended_quantity)} /{" "}
                                  {formatNumber(item.available_quantity)} units
                                </td>
                                <td data-label="Status">
                                  <StatusBadge status={hasShortfall ? "limited" : "available"} />
                                </td>
                              </tr>
                            );
                          })}
                          {rec.unavailable_needs.map((gap, idx) => (
                            <tr key={`${rec.id}-gap-${idx}`} className="row-shortage">
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
                        <div
                          key={`why-${rec.id}-${item.resource_id}`}
                          className="why-item why-item-match"
                        >
                          <div className="why-item-head">
                            <Icon name="checkCircle" size={14} />
                            <strong>Matched · {item.resource_name}</strong>
                          </div>
                          <p>{item.explanation}</p>
                        </div>
                      ))}
                      {(rec.insufficient_needs || []).map((shortfall, idx) => (
                        <div key={`sh-${rec.id}-${idx}`} className="why-item why-item-warn">
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
                        <div key={`un-${rec.id}-${idx}`} className="why-item why-item-danger">
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

                  {isPending ? (
                    <div className="decision-box">
                      <div className="form-field">
                        <label htmlFor={`rec-page-note-${rec.id}`}>
                          Decision Note (optional, max 300 characters)
                        </label>
                        <textarea
                          id={`rec-page-note-${rec.id}`}
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
                          onClick={() => setConfirmState({ rec, decision: "approved" })}
                        >
                          <Icon name="checkCircle" size={15} />
                          <span>Approve Recommendation</span>
                        </button>
                        <button
                          type="button"
                          className="btn btn-danger-outline"
                          onClick={() => setConfirmState({ rec, decision: "rejected" })}
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
                        <strong>Operator Note:</strong> {rec.decision_note || "No note entered."}
                      </p>
                    </div>
                  )}
                </article>
              );
            })}
          </div>
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
