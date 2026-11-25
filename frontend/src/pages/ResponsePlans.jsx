import React, { useCallback, useEffect, useMemo, useState } from "react";
import { CodeBadge, StatusBadge } from "../components/common/Badge";
import EmptyState from "../components/common/EmptyState";
import ErrorState from "../components/common/ErrorState";
import Icon from "../components/common/Icon";
import { SkeletonTable } from "../components/common/Skeleton";
import { useData } from "../context/DataContext";
import { useToast } from "../context/ToastContext";
import { describeError } from "../services/apiClient";
import {
  completeResponsePlan,
  createResponsePlan,
  decideResponsePlan,
  listResponsePlans,
} from "../services/responsePlanService";
import {
  formatDateTime,
  formatNumber,
  incidentCode,
  labelize,
  recommendationCode,
  resourceCode,
} from "../utils/format";

const PLAN_DISCLAIMER =
  "Academic simulation only. No emergency service is contacted, no vehicle/team is dispatched, and physical inventory quantities are not changed.";

function planCode(id) {
  return `PLAN-${String(id).padStart(4, "0")}`;
}

export default function ResponsePlans() {
  const { recommendations, incidentIndex, refreshing, refreshAll } = useData();
  const toast = useToast();

  const [plans, setPlans] = useState({ data: [], disclaimer: PLAN_DISCLAIMER, loading: true, error: null });
  const [selectedRecommendation, setSelectedRecommendation] = useState("");
  const [notes, setNotes] = useState({});
  const [creating, setCreating] = useState(false);
  const [workingPlanId, setWorkingPlanId] = useState(null);

  const loadPlans = useCallback(async () => {
    setPlans((current) => ({ ...current, loading: current.data.length === 0, error: null }));
    try {
      const result = await listResponsePlans();
      setPlans({ data: result.plans, disclaimer: result.disclaimer, loading: false, error: null });
    } catch (error) {
      setPlans((current) => ({ ...current, loading: false, error }));
    }
  }, []);

  useEffect(() => {
    loadPlans();
  }, [loadPlans]);

  const usedRecommendationIds = useMemo(
    () => new Set(plans.data.map((plan) => plan.recommendation_id)),
    [plans.data]
  );
  const eligibleRecommendations = useMemo(
    () => recommendations.filter(
      (item) => item.status === "approved" && !usedRecommendationIds.has(item.id) && item.items.length > 0
    ),
    [recommendations, usedRecommendationIds]
  );

  const counts = useMemo(() => ({
    pending: plans.data.filter((plan) => plan.status === "pending").length,
    simulated: plans.data.filter((plan) => plan.status === "simulated").length,
    completed: plans.data.filter((plan) => plan.status === "completed").length,
    rejected: plans.data.filter((plan) => plan.status === "rejected").length,
  }), [plans.data]);

  async function handleCreatePlan(event) {
    event.preventDefault();
    if (creating || !selectedRecommendation) return;
    const recommendation = recommendations.find((item) => item.id === Number(selectedRecommendation));
    if (!recommendation) return;

    setCreating(true);
    try {
      const created = await createResponsePlan(recommendation.incident_id, recommendation.id);
      await loadPlans();
      setSelectedRecommendation("");
      toast({
        type: "success",
        title: `${planCode(created.id)} created`,
        message: "The plan is pending a second operator approval before simulation.",
      });
    } catch (error) {
      toast({
        type: "error",
        title: "Could not create response plan",
        message: describeError(error),
      });
    } finally {
      setCreating(false);
    }
  }

  async function handleDecision(plan, decision) {
    if (workingPlanId !== null) return;
    setWorkingPlanId(plan.id);
    try {
      const result = await decideResponsePlan(plan.id, decision, notes[plan.id] || "");
      await loadPlans();
      toast({
        type: decision === "approve" ? "success" : "info",
        title: `${planCode(plan.id)} ${decision === "approve" ? "simulation approved" : "rejected"}`,
        message: result.message,
      });
    } catch (error) {
      toast({
        type: "error",
        title: "Response plan could not be updated",
        message: describeError(error),
      });
      await loadPlans();
    } finally {
      setWorkingPlanId(null);
    }
  }

  async function handleComplete(plan) {
    if (workingPlanId !== null) return;
    setWorkingPlanId(plan.id);
    try {
      await completeResponsePlan(plan.id, notes[plan.id] || "");
      await loadPlans();
      toast({
        type: "success",
        title: `${planCode(plan.id)} completed`,
        message: "Simulation reservation released. Physical inventory was never changed.",
      });
    } catch (error) {
      toast({
        type: "error",
        title: "Could not complete simulation",
        message: describeError(error),
      });
    } finally {
      setWorkingPlanId(null);
    }
  }

  return (
    <div className="page-stack">
      <section className="page-hero">
        <div>
          <h2 className="page-heading">Response Plan Simulation</h2>
          <p className="page-subheading">
            Turn an approved resource recommendation into a human-reviewed allocation simulation.
            This page does not dispatch real teams or contact emergency services.
          </p>
        </div>
        <div className="page-hero-actions">
          <button type="button" className="btn btn-secondary" onClick={loadPlans} disabled={plans.loading}>
            <Icon name="refresh" size={15} />
            <span>Refresh Plans</span>
          </button>
          <button type="button" className="btn btn-secondary" onClick={refreshAll} disabled={refreshing}>
            <Icon name="refresh" size={15} />
            <span>Refresh Data</span>
          </button>
        </div>
      </section>

      <div className="review-banner">
        <Icon name="shield" size={16} />
        <span>{PLAN_DISCLAIMER}</span>
      </div>

      <section className="stats-grid" aria-label="Response plan status summary">
        <article className="surface-card stat-card">
          <div className="stat-label">Awaiting Approval</div>
          <div className="stat-value tabular">{formatNumber(counts.pending)}</div>
          <div className="stat-meta">Plans requiring an operator decision</div>
        </article>
        <article className="surface-card stat-card">
          <div className="stat-label">Simulated</div>
          <div className="stat-value tabular">{formatNumber(counts.simulated)}</div>
          <div className="stat-meta">Active reservations in the simulation ledger</div>
        </article>
        <article className="surface-card stat-card">
          <div className="stat-label">Completed</div>
          <div className="stat-value tabular">{formatNumber(counts.completed)}</div>
          <div className="stat-meta">Simulation reservations released</div>
        </article>
        <article className="surface-card stat-card">
          <div className="stat-label">Rejected</div>
          <div className="stat-value tabular">{formatNumber(counts.rejected)}</div>
          <div className="stat-meta">Plans not approved for simulation</div>
        </article>
      </section>

      <section className="surface-card">
        <div className="panel-header">
          <div>
            <h3 className="section-title">Create a Simulation Plan</h3>
            <p className="section-subtitle">
              Only approved recommendations with at least one matched resource can be used.
              Creating a plan does not reserve stock.
            </p>
          </div>
        </div>
        {eligibleRecommendations.length === 0 ? (
          <div className="notice-box">
            <Icon name="info" size={16} />
            <div>
              <strong>No approved recommendations are available</strong>
              <p>Review and approve a resource recommendation first. Then return here to create its simulation plan.</p>
            </div>
          </div>
        ) : (
          <form className="toolbar-row" onSubmit={handleCreatePlan}>
            <div className="filter-group" style={{ flex: 1 }}>
              <select
                aria-label="Choose an approved recommendation"
                value={selectedRecommendation}
                onChange={(event) => setSelectedRecommendation(event.target.value)}
                required
              >
                <option value="">Select approved recommendation…</option>
                {eligibleRecommendations.map((item) => (
                  <option key={item.id} value={item.id}>
                    {recommendationCode(item.id)} · {incidentCode(item.incident_id)} · {item.items.length} resource pool(s)
                  </option>
                ))}
              </select>
            </div>
            <button type="submit" className="btn btn-primary" disabled={!selectedRecommendation || creating}>
              <Icon name="checkCircle" size={15} />
              <span>{creating ? "Creating..." : "Create Pending Plan"}</span>
            </button>
          </form>
        )}
      </section>

      {plans.error ? (
        <ErrorState
          title="Could not load response plans"
          error={plans.error}
          onRetry={loadPlans}
        />
      ) : plans.loading && plans.data.length === 0 ? (
        <SkeletonTable rows={4} />
      ) : plans.data.length === 0 ? (
        <EmptyState
          icon="truck"
          title="No response plans yet"
          description="Approve a resource recommendation, then create a pending simulation plan above."
          actionLabel="Open Recommendations"
          onAction={() => { window.location.hash = "#/recommendations"; }}
        />
      ) : (
        <section className="surface-card">
          <div className="panel-header">
            <div>
              <h3 className="section-title">Response Plans &amp; Audit Trail</h3>
              <p className="section-subtitle">
                Simulated plans reserve quantities only in this ledger. Completed or rejected plans hold no reservations.
              </p>
            </div>
            <CodeBadge>{plans.data.length} plan(s)</CodeBadge>
          </div>

          <div className="rec-stack">
            {plans.data.map((plan) => {
              const incident = incidentIndex[plan.incident_id];
              const busy = workingPlanId === plan.id;
              return (
                <article key={plan.id} className="rec-panel">
                  <div className="rec-panel-header">
                    <div className="rec-panel-title-row">
                      <CodeBadge>{planCode(plan.id)}</CodeBadge>
                      <StatusBadge status={plan.status} />
                      <CodeBadge>{incidentCode(plan.incident_id)}</CodeBadge>
                      <CodeBadge>{recommendationCode(plan.recommendation_id)}</CodeBadge>
                    </div>
                    <span className="text-muted tabular">Created {formatDateTime(plan.created_at)}</span>
                  </div>

                  <p className="rec-summary-line">
                    {plan.summary}
                    {incident ? ` · ${labelize(incident.hazard_type)} — ${incident.location}` : ""}
                  </p>

                  <div className="table-scroll">
                    <table className="data-table compact-table">
                      <thead>
                        <tr>
                          <th>Resource</th>
                          <th>Depot</th>
                          <th>Quantity</th>
                          <th>Straight-line Distance</th>
                        </tr>
                      </thead>
                      <tbody>
                        {plan.items.map((item) => (
                          <tr key={item.id}>
                            <td data-label="Resource">
                              <div className="font-medium">{item.resource_name} <CodeBadge>{resourceCode(item.resource_id)}</CodeBadge></div>
                              <div className="cell-sub">{labelize(item.resource_type)}</div>
                            </td>
                            <td data-label="Depot">{item.resource_location}</td>
                            <td data-label="Quantity" className="tabular">{formatNumber(item.assigned_quantity)} unit(s)</td>
                            <td data-label="Straight-line Distance" className="tabular">
                              {typeof item.distance_km === "number" ? `${item.distance_km.toFixed(2)} km` : "Not calculated"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  {plan.decision_note && (
                    <div className="notice-box">
                      <Icon name="info" size={15} />
                      <div><strong>Decision note</strong><p>{plan.decision_note}</p></div>
                    </div>
                  )}

                  {plan.status === "pending" && (
                    <div className="form-grid" style={{ marginTop: 14 }}>
                      <div className="form-field form-field-full">
                        <label htmlFor={`plan-note-${plan.id}`}>Operator note (optional)</label>
                        <textarea
                          id={`plan-note-${plan.id}`}
                          rows={2}
                          maxLength={500}
                          value={notes[plan.id] || ""}
                          onChange={(event) => setNotes((current) => ({ ...current, [plan.id]: event.target.value }))}
                          placeholder="Record why this plan should or should not be simulated…"
                          disabled={busy}
                        />
                      </div>
                      <div className="page-hero-actions">
                        <button type="button" className="btn btn-primary" onClick={() => handleDecision(plan, "approve")} disabled={busy}>
                          <Icon name="checkCircle" size={15} />
                          <span>{busy ? "Saving..." : "Approve & Simulate"}</span>
                        </button>
                        <button type="button" className="btn btn-danger" onClick={() => handleDecision(plan, "reject")} disabled={busy}>
                          <Icon name="xCircle" size={15} />
                          <span>Reject Plan</span>
                        </button>
                      </div>
                    </div>
                  )}

                  {plan.status === "simulated" && (
                    <div className="notice-box">
                      <Icon name="activity" size={15} />
                      <div>
                        <strong>Simulation reservations are active</strong>
                        <p>These quantities are reserved only in the prototype ledger. Mark complete to release them.</p>
                      </div>
                      <button type="button" className="btn btn-secondary btn-sm" onClick={() => handleComplete(plan)} disabled={busy}>
                        <Icon name="check" size={14} />
                        <span>{busy ? "Completing..." : "Complete Simulation"}</span>
                      </button>
                    </div>
                  )}

                  <div className="timeline-list" style={{ marginTop: 14 }}>
                    {plan.actions.map((action) => (
                      <div key={action.id} className="timeline-item">
                        <span className="timeline-dot" />
                        <div className="timeline-copy">
                          <strong>{labelize(action.action)}</strong>
                          <p>{action.note || "No note recorded."}</p>
                          <span className="text-muted tabular">{formatDateTime(action.created_at)}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </article>
              );
            })}
          </div>
        </section>
      )}
    </div>
  );
}
