import React, { useCallback, useEffect, useMemo, useState } from "react";
import { CodeBadge, StatusBadge } from "../components/common/Badge";
import EmptyState from "../components/common/EmptyState";
import ErrorState from "../components/common/ErrorState";
import Icon from "../components/common/Icon";
import { SkeletonTable } from "../components/common/Skeleton";
import { useToast } from "../context/ToastContext";
import { useData } from "../context/DataContext";
import { navigate } from "../hooks/useHashRoute";
import { describeError } from "../services/apiClient";
import {
  listAlertAssessments,
  listAlertSources,
  listAlerts,
  promoteAlertToIncident,
  reviewAlert,
  runAlertAssessment,
  syncAlertFeeds,
} from "../services/alertService";
import {
  formatDateTime,
  formatNumber,
  formatRelative,
  incidentCode,
  labelize,
  toLocalInputValue,
} from "../utils/format";

const HAZARD_OPTIONS = [
  "earthquake",
  "flood",
  "cyclone",
  "wildfire",
  "volcano",
  "drought",
  "landslide",
  "fire",
  "other",
];


function safeExternalUrl(value) {
  if (typeof value !== "string" || !value.trim()) return null;
  try {
    const url = new URL(value);
    return url.protocol === "https:" || url.protocol === "http:" ? url.href : null;
  } catch {
    return null;
  }
}

function AlertLevel({ level }) {
  if (!level) return <span className="alert-level-badge alert-level-unknown">No level</span>;
  const value = String(level).toLowerCase();
  return <span className={`alert-level-badge alert-level-${value}`}>{value.toUpperCase()}</span>;
}

function SourceCard({ source }) {
  const last = source.last_sync;
  const healthy = last?.status === "success";
  return (
    <article className="surface-card alert-source-card">
      <div className="alert-source-top">
        <div>
          <div className="alert-source-name">{source.name}</div>
          <div className="cell-sub">{source.source.toUpperCase()} · {source.hazard_types.map(labelize).join(", ")}</div>
        </div>
        {last ? (
          <StatusBadge status={healthy ? "available" : "unavailable"} />
        ) : (
          <StatusBadge status="pending" />
        )}
      </div>
      <div className="alert-source-stats">
        <div>
          <span className="stat-label">Fetched last sync</span>
          <strong className="tabular">{formatNumber(last?.fetched_count ?? 0)}</strong>
        </div>
        <div>
          <span className="stat-label">New records</span>
          <strong className="tabular">{formatNumber(last?.created_count ?? 0)}</strong>
        </div>
        <div>
          <span className="stat-label">Updated records</span>
          <strong className="tabular">{formatNumber(last?.updated_count ?? 0)}</strong>
        </div>
      </div>
      <div className="alert-source-footer">
        <span className="text-muted">{last ? `Last sync ${formatRelative(last.finished_at)}` : "Not synced yet"}</span>
        <a href={source.feed_url} target="_blank" rel="noreferrer">Provider feed ↗</a>
      </div>
      {last?.error_message && (
        <p className="field-error alert-source-error">{last.error_message}</p>
      )}
      <p className="cell-sub">{source.update_interval}</p>
    </article>
  );
}

function agentMetric(key, result) {
  if (key === "evidence_quality") {
    return `${result.completeness_score ?? "—"}/100 · ${labelize(result.completeness_grade)}`;
  }
  if (key === "hazard_signal") {
    const value = result.magnitude ?? result.provider_alert_level ?? result.signal;
    const unit = result.magnitude_unit || "";
    return `${labelize(result.signal)}${value !== undefined && value !== null ? ` · ${value} ${unit}` : ""}`;
  }
  if (key === "event_recency") {
    return result.event_age_hours === null
      ? labelize(result.recency_band)
      : `${labelize(result.recency_band)} · ${result.event_age_hours} h`;
  }
  if (key === "location_evidence") {
    return `${labelize(result.location_status)} · Population exposure: ${result.population_exposure}`;
  }
  if (key === "review_coordinator") {
    return labelize(result.review_priority);
  }
  return labelize(result.status);
}

function AssessmentPanel({ assessment }) {
  const agents = assessment.agents || {};
  return (
    <section className="alert-assessment-panel">
      <div className="alert-assessment-head">
        <div>
          <strong>Specialist-agent assessment</strong>
          <p className="cell-sub">{assessment.summary}</p>
        </div>
        <span className="alert-priority-pill">{labelize(assessment.review_priority)}</span>
      </div>
      <div className="alert-agent-grid">
        {Object.entries(agents).map(([key, result]) => (
          <article className="alert-agent-card" key={key}>
            <div className="alert-agent-title">{labelize(key)}</div>
            <div className="alert-agent-metric">{agentMetric(key, result)}</div>
            {result.explanation && <p className="cell-sub">{result.explanation}</p>}
            {Array.isArray(result.reasons) && result.reasons.length > 0 && (
              <ul className="alert-agent-reasons">
                {result.reasons.map((reason, index) => <li key={index}>{reason}</li>)}
              </ul>
            )}
            <details>
              <summary>View agent output</summary>
              <pre className="alert-agent-json">{JSON.stringify(result, null, 2)}</pre>
            </details>
          </article>
        ))}
      </div>
      <p className="alert-disclaimer">{assessment.disclaimer}</p>
    </section>
  );
}

export default function Alerts() {
  const toast = useToast();
  const { refreshAll } = useData();
  const [alerts, setAlerts] = useState([]);
  const [sources, setSources] = useState([]);
  const [totalCount, setTotalCount] = useState(0);
  const [disclaimer, setDisclaimer] = useState("");
  const [updatedAt, setUpdatedAt] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [sourceFilter, setSourceFilter] = useState("all");
  const [hazardFilter, setHazardFilter] = useState("all");
  const [levelFilter, setLevelFilter] = useState("all");
  const [reviewFilter, setReviewFilter] = useState("all");

  const [syncing, setSyncing] = useState(false);
  const [workingAlertId, setWorkingAlertId] = useState(null);
  const [reviewNotes, setReviewNotes] = useState({});
  const [assessments, setAssessments] = useState({});
  const [assessmentHistory, setAssessmentHistory] = useState({});
  const [assessingAlertId, setAssessingAlertId] = useState(null);
  const [promotingAlertId, setPromotingAlertId] = useState(null);
  const [promotionForm, setPromotionForm] = useState(null);
  const [promotionError, setPromotionError] = useState(null);

  const loadData = useCallback(async ({ silent = false } = {}) => {
    if (!silent) setLoading(true);
    setError(null);
    try {
      const [list, sourceList] = await Promise.all([
        listAlerts({
          source: sourceFilter,
          hazardType: hazardFilter,
          alertLevel: levelFilter,
          reviewStatus: reviewFilter,
          limit: 500,
          offset: 0,
        }),
        listAlertSources(),
      ]);
      setAlerts(list.alerts);
      setTotalCount(list.total_count);
      setDisclaimer(list.disclaimer);
      setSources(sourceList);
      setUpdatedAt(new Date());
    } catch (err) {
      setError(err);
    } finally {
      if (!silent) setLoading(false);
    }
  }, [sourceFilter, hazardFilter, levelFilter, reviewFilter]);

  useEffect(() => {
    loadData();
    const timer = setInterval(() => loadData({ silent: true }), 60000);
    return () => clearInterval(timer);
  }, [loadData]);

  const counts = useMemo(() => ({
    new: alerts.filter((alert) => alert.review_status === "new").length,
    reviewed: alerts.filter((alert) => alert.review_status === "reviewed").length,
    dismissed: alerts.filter((alert) => alert.review_status === "dismissed").length,
    red: alerts.filter((alert) => alert.alert_level === "red").length,
  }), [alerts]);

  async function handleSync() {
    if (syncing) return;
    setSyncing(true);
    try {
      const result = await syncAlertFeeds(["gdacs", "usgs"]);
      await loadData({ silent: true });
      toast({
        type: result.status === "failed" ? "error" : result.status === "partial" ? "warning" : "success",
        title: "Feed synchronization finished",
        message: `${formatNumber(result.fetched_count)} fetched · ${formatNumber(result.created_count)} new · ${formatNumber(result.updated_count)} updated · ${result.status}`,
      });
    } catch (err) {
      toast({ type: "error", title: "Feed synchronization failed", message: describeError(err) });
    } finally {
      setSyncing(false);
    }
  }

  async function handleReview(alert, status) {
    if (workingAlertId !== null) return;
    setWorkingAlertId(alert.id);
    try {
      await reviewAlert(alert.id, status, reviewNotes[alert.id] || "");
      await loadData({ silent: true });
      toast({
        type: "success",
        title: `Alert #${alert.id} ${status}`,
        message: "The operator review decision has been recorded.",
      });
    } catch (err) {
      toast({ type: "error", title: "Could not record review", message: describeError(err) });
    } finally {
      setWorkingAlertId(null);
    }
  }

  function startPromotion(alert) {
    if (alert.review_status !== "reviewed" || alert.linked_incident_id) return;
    const supportedHazards = new Set([
      "flood", "earthquake", "fire", "cyclone", "landslide",
      "building_collapse", "chemical_spill", "other",
    ]);
    const eventDate = alert.event_at ? new Date(alert.event_at) : new Date();
    const validDate = Number.isNaN(eventDate.getTime()) ? new Date() : eventDate;

    setPromotionForm({
      hazard_type: supportedHazards.has(alert.hazard_type) ? alert.hazard_type : "other",
      description: String(alert.description || alert.title || "").slice(0, 1000),
      location: alert.location || alert.country || "",
      reported_at: toLocalInputValue(validDate),
      people_affected: "",
      help_needed: [],
      latitude: alert.latitude === null ? "" : String(alert.latitude),
      longitude: alert.longitude === null ? "" : String(alert.longitude),
    });
    setPromotionError(null);
    setPromotingAlertId(alert.id);
  }

  function updatePromotionField(field, value) {
    setPromotionForm((current) => current ? { ...current, [field]: value } : current);
  }

  function togglePromotionHelp(helpType, checked) {
    setPromotionForm((current) => {
      if (!current) return current;
      const next = checked
        ? [...current.help_needed, helpType]
        : current.help_needed.filter((item) => item !== helpType);
      return { ...current, help_needed: next };
    });
  }

  async function handlePromotionSubmit(event, alert) {
    event.preventDefault();
    if (!promotionForm || promotingAlertId !== alert.id) return;
    setPromotionError(null);

    const peopleText = String(promotionForm.people_affected).trim();
    const people = Number(peopleText);
    if (!peopleText || !Number.isInteger(people) || people < 0 || people > 1000000) {
      setPromotionError("Enter the operator-verified affected-person count (0 to 1,000,000).");
      return;
    }
    if (promotionForm.help_needed.length === 0) {
      setPromotionError("Select at least one type of help required.");
      return;
    }
    const hasLatitude = String(promotionForm.latitude).trim() !== "";
    const hasLongitude = String(promotionForm.longitude).trim() !== "";
    if (hasLatitude !== hasLongitude) {
      setPromotionError("Provide both coordinates or leave both empty.");
      return;
    }
    const latitude = hasLatitude ? Number(promotionForm.latitude) : null;
    const longitude = hasLongitude ? Number(promotionForm.longitude) : null;
    if (
      (hasLatitude && (!Number.isFinite(latitude) || latitude < -90 || latitude > 90)) ||
      (hasLongitude && (!Number.isFinite(longitude) || longitude < -180 || longitude > 180))
    ) {
      setPromotionError("Coordinates are outside the allowed latitude/longitude ranges.");
      return;
    }
    const reportedAt = new Date(promotionForm.reported_at);
    if (Number.isNaN(reportedAt.getTime())) {
      setPromotionError("Enter a valid event/report timestamp.");
      return;
    }

    const payload = {
      hazard_type: promotionForm.hazard_type,
      description: promotionForm.description.trim(),
      location: promotionForm.location.trim(),
      reported_at: reportedAt.toISOString(),
      people_affected: people,
      help_needed: promotionForm.help_needed,
      latitude,
      longitude,
    };
    if (payload.description.length < 10 || payload.location.length < 2) {
      setPromotionError("Description must be at least 10 characters and location at least 2 characters.");
      return;
    }

    setWorkingAlertId(alert.id);
    try {
      const result = await promoteAlertToIncident(alert.id, payload);
      setPromotingAlertId(null);
      setPromotionForm(null);
      await loadData({ silent: true });
      await refreshAll();
      toast({
        type: "success",
        title: `Incident ${incidentCode(result.incident.id)} created`,
        message: "The reviewed external alert is linked to the new incident and now appears in the incident priority workflow.",
      });
    } catch (err) {
      const message = describeError(err);
      setPromotionError(message);
      toast({ type: "error", title: "Could not create incident", message });
    } finally {
      setWorkingAlertId(null);
    }
  }

  async function handleAssessment(alert) {
    if (assessingAlertId !== null) return;
    setAssessingAlertId(alert.id);
    try {
      const assessment = await runAlertAssessment(alert.id);
      setAssessments((current) => ({ ...current, [alert.id]: assessment }));
      toast({
        type: "success",
        title: "Agent assessment completed",
        message: `Review priority: ${labelize(assessment.review_priority)}. Human review remains required.`,
      });
    } catch (err) {
      toast({ type: "error", title: "Assessment failed", message: describeError(err) });
    } finally {
      setAssessingAlertId(null);
    }
  }

  async function handleAssessmentHistory(alert) {
    if (assessingAlertId !== null) return;
    setAssessingAlertId(alert.id);
    try {
      const history = await listAlertAssessments(alert.id);
      setAssessmentHistory((current) => ({ ...current, [alert.id]: history.assessments }));
      if (history.assessments.length > 0 && !assessments[alert.id]) {
        setAssessments((current) => ({ ...current, [alert.id]: history.assessments[0] }));
      }
      toast({
        type: "info",
        title: "Assessment history loaded",
        message: `${formatNumber(history.count)} saved assessment(s) for alert #${alert.id}.`,
      });
    } catch (err) {
      toast({ type: "error", title: "Could not load assessment history", message: describeError(err) });
    } finally {
      setAssessingAlertId(null);
    }
  }

  const newCount = sources.reduce((sum, source) => sum + (source.last_sync?.created_count || 0), 0);
  const failedSources = sources.filter((source) => source.last_sync?.status === "failed").length;

  return (
    <div className="page-stack">
      <section className="page-hero">
        <div>
          <h2 className="page-heading">Alert Intelligence</h2>
          <p className="page-subheading">
            Monitor external disaster reports, inspect their source evidence, and run the specialist-agent review pipeline.
          </p>
        </div>
        <div className="page-hero-actions">
          {updatedAt && <span className="last-sync tabular">Updated {formatRelative(updatedAt)}</span>}
          <button type="button" className="btn btn-secondary" onClick={() => loadData()} disabled={loading}>
            <Icon name="refresh" size={15} />
            <span>Refresh List</span>
          </button>
          <button type="button" className="btn btn-primary" onClick={handleSync} disabled={syncing}>
            <Icon name="activity" size={15} className={syncing ? "spin" : ""} />
            <span>{syncing ? "Syncing providers..." : "Sync Public Feeds"}</span>
          </button>
        </div>
      </section>

      <div className="review-banner">
        <Icon name="shield" size={16} />
        <span>Imported alerts are unverified reports, not confirmed incidents or emergency instructions. Agent assessments support human review only; they do not create incidents or dispatch resources.</span>
      </div>

      <section className="stats-grid" aria-label="Alert summary">
        <article className="surface-card stat-card">
          <div className="stat-label">Alerts in current view</div>
          <div className="stat-value tabular">{formatNumber(totalCount)}</div>
          <div className="stat-meta">Filtered external alert records</div>
        </article>
        <article className="surface-card stat-card">
          <div className="stat-label">New / unreviewed</div>
          <div className="stat-value tabular">{formatNumber(counts.new)}</div>
          <div className="stat-meta">Awaiting operator review in this page</div>
        </article>
        <article className="surface-card stat-card">
          <div className="stat-label">Red provider alerts</div>
          <div className="stat-value tabular">{formatNumber(counts.red)}</div>
          <div className="stat-meta">Provider alert level, not local damage grade</div>
        </article>
        <article className="surface-card stat-card">
          <div className="stat-label">Feed sync failures</div>
          <div className="stat-value tabular">{formatNumber(failedSources)}</div>
          <div className="stat-meta">{formatNumber(newCount)} new records in latest sync runs</div>
        </article>
      </section>

      <section className="alert-source-grid">
        {sources.map((source) => <SourceCard key={source.source} source={source} />)}
      </section>

      <section className="surface-card">
        <div className="panel-header">
          <div>
            <h3 className="section-title">External Disaster Reports</h3>
            <p className="section-subtitle">
              Provider data is retained with source identifiers and links. The list auto-refreshes every 60 seconds; feed synchronization is manual.
            </p>
          </div>
          <CodeBadge>{formatNumber(totalCount)} record(s)</CodeBadge>
        </div>

        <div className="toolbar-row alert-filter-row">
          <div className="filter-group">
            <select value={sourceFilter} onChange={(event) => setSourceFilter(event.target.value)} aria-label="Filter by source">
              <option value="all">All sources</option>
              <option value="gdacs">GDACS</option>
              <option value="usgs">USGS</option>
            </select>
            <select value={hazardFilter} onChange={(event) => setHazardFilter(event.target.value)} aria-label="Filter by hazard">
              <option value="all">All hazards</option>
              {HAZARD_OPTIONS.map((hazard) => <option key={hazard} value={hazard}>{labelize(hazard)}</option>)}
            </select>
            <select value={levelFilter} onChange={(event) => setLevelFilter(event.target.value)} aria-label="Filter by provider alert level">
              <option value="all">All provider levels</option>
              <option value="red">Red</option>
              <option value="orange">Orange</option>
              <option value="green">Green</option>
            </select>
            <select value={reviewFilter} onChange={(event) => setReviewFilter(event.target.value)} aria-label="Filter by review status">
              <option value="all">All review states</option>
              <option value="new">New</option>
              <option value="reviewed">Reviewed</option>
              <option value="dismissed">Dismissed</option>
            </select>
          </div>
        </div>

        {error ? (
          <ErrorState title="Could not load external alerts" error={error} onRetry={() => loadData()} />
        ) : loading ? (
          <SkeletonTable rows={5} />
        ) : alerts.length === 0 ? (
          <EmptyState
            icon="alert"
            title="No external alerts match these filters"
            description="Try another filter or synchronize the GDACS and USGS public feeds."
            actionLabel="Sync Public Feeds"
            onAction={handleSync}
            secondaryActionLabel="Clear Filters"
            onSecondaryAction={() => {
              setSourceFilter("all");
              setHazardFilter("all");
              setLevelFilter("all");
              setReviewFilter("all");
            }}
          />
        ) : (
          <div className="alert-list">
            {alerts.map((alert) => {
              const assessment = assessments[alert.id];
              const sourceUrl = safeExternalUrl(alert.source_url);
              const busy = workingAlertId === alert.id;
              return (
                <article className="alert-card" key={alert.id}>
                  <div className="alert-card-head">
                    <div className="alert-card-title-group">
                      <div className="alert-card-title-row">
                        <strong>{alert.title}</strong>
                        <AlertLevel level={alert.alert_level} />
                        <StatusBadge status={alert.review_status} />
                      </div>
                      <div className="cell-sub">
                        {alert.source.toUpperCase()} · {labelize(alert.hazard_type)} · Event {alert.source_event_id}
                      </div>
                    </div>
                    <CodeBadge>ALT-{String(alert.id).padStart(4, "0")}</CodeBadge>
                  </div>

                  <div className="alert-meta-grid">
                    <div><span>Location</span><strong>{alert.location || alert.country || "Not supplied"}</strong></div>
                    <div><span>Event time</span><strong>{formatDateTime(alert.event_at)}</strong></div>
                    <div><span>Severity signal</span><strong>{alert.severity_text || (alert.severity_value !== null ? `${alert.severity_value} ${alert.severity_unit || ""}` : "Not supplied")}</strong></div>
                    <div><span>Coordinates</span><strong className="tabular">{alert.latitude !== null && alert.longitude !== null ? `${alert.latitude.toFixed(4)}, ${alert.longitude.toFixed(4)}` : "Not supplied"}</strong></div>
                    <div><span>Last seen</span><strong>{formatRelative(alert.last_seen_at)}</strong></div>
                    <div><span>Review state</span><strong>{labelize(alert.review_status)}</strong></div>
                  </div>

                  {alert.description && <p className="alert-description">{alert.description}</p>}
                  {alert.review_note && (
                    <div className="notice-box">
                      <Icon name="info" size={14} />
                      <div><strong>Saved operator review note</strong><p>{alert.review_note}</p></div>
                    </div>
                  )}

                  <div className="alert-card-actions">
                    {sourceUrl && (
                      <a className="btn btn-secondary btn-sm" href={sourceUrl} target="_blank" rel="noopener noreferrer">
                        <Icon name="arrowRight" size={14} />
                        <span>Open source report</span>
                      </a>
                    )}
                    <button type="button" className="btn btn-secondary btn-sm" onClick={() => handleAssessment(alert)} disabled={assessingAlertId !== null}>
                      <Icon name="cpu" size={14} />
                      <span>{assessingAlertId === alert.id ? "Assessing..." : "Run agent assessment"}</span>
                    </button>
                    <button type="button" className="btn btn-secondary btn-sm" onClick={() => handleAssessmentHistory(alert)} disabled={assessingAlertId !== null}>
                      <Icon name="history" size={14} />
                      <span>Assessment history</span>
                    </button>
                    {alert.review_status === "reviewed" && !alert.linked_incident_id && (
                      <button type="button" className="btn btn-primary btn-sm" onClick={() => startPromotion(alert)} disabled={promotingAlertId !== null}>
                        <Icon name="plus" size={14} />
                        <span>Create incident</span>
                      </button>
                    )}
                    {alert.linked_incident_id && (
                      <button type="button" className="btn btn-secondary btn-sm" onClick={() => navigate(`#/incidents/${alert.linked_incident_id}`)}>
                        <Icon name="externalLink" size={14} />
                        <span>Open linked incident {incidentCode(alert.linked_incident_id)}</span>
                      </button>
                    )}
                    {alert.review_status === "new" && (
                      <>
                        <button type="button" className="btn btn-secondary btn-sm" onClick={() => handleReview(alert, "reviewed")} disabled={busy}>
                          <Icon name="checkCircle" size={14} />
                          <span>Mark reviewed</span>
                        </button>
                        <button type="button" className="btn btn-danger btn-sm" onClick={() => handleReview(alert, "dismissed")} disabled={busy}>
                          <Icon name="xCircle" size={14} />
                          <span>Dismiss</span>
                        </button>
                      </>
                    )}
                  </div>

                  {alert.review_status === "new" && (
                    <div className="alert-review-note">
                      <label htmlFor={`alert-note-${alert.id}`}>Operator review note (optional)</label>
                      <input
                        id={`alert-note-${alert.id}`}
                        type="text"
                        maxLength={500}
                        value={reviewNotes[alert.id] || ""}
                        onChange={(event) => setReviewNotes((current) => ({ ...current, [alert.id]: event.target.value }))}
                        placeholder="Record the source bulletin check or reason for dismissal…"
                        disabled={busy}
                      />
                    </div>
                  )}

                  {promotingAlertId === alert.id && promotionForm && (
                    <form className="alert-promotion-form" onSubmit={(event) => handlePromotionSubmit(event, alert)}>
                      <div className="alert-promotion-head">
                        <div>
                          <strong>Create an incident from this reviewed alert</strong>
                          <p className="cell-sub">Confirm every incident field. Provider data does not supply affected-person counts or required help types.</p>
                        </div>
                        <button type="button" className="btn btn-secondary btn-xs" onClick={() => { setPromotingAlertId(null); setPromotionForm(null); setPromotionError(null); }} disabled={busy}>
                          Cancel
                        </button>
                      </div>

                      <div className="alert-promotion-grid">
                        <div className="form-field">
                          <label htmlFor={`promote-hazard-${alert.id}`}>Incident hazard type</label>
                          <select id={`promote-hazard-${alert.id}`} value={promotionForm.hazard_type} onChange={(event) => updatePromotionField("hazard_type", event.target.value)} disabled={busy}>
                            {["flood", "earthquake", "fire", "cyclone", "landslide", "building_collapse", "chemical_spill", "other"].map((value) => (
                              <option key={value} value={value}>{labelize(value)}</option>
                            ))}
                          </select>
                        </div>

                        <div className="form-field">
                          <label htmlFor={`promote-location-${alert.id}`}>Incident location</label>
                          <input id={`promote-location-${alert.id}`} value={promotionForm.location} onChange={(event) => updatePromotionField("location", event.target.value)} minLength={2} maxLength={200} required disabled={busy} />
                        </div>

                        <div className="form-field">
                          <label htmlFor={`promote-reported-${alert.id}`}>Reported/event time</label>
                          <input id={`promote-reported-${alert.id}`} type="datetime-local" value={promotionForm.reported_at} onChange={(event) => updatePromotionField("reported_at", event.target.value)} required disabled={busy} />
                        </div>

                        <div className="form-field">
                          <label htmlFor={`promote-people-${alert.id}`}>People affected (operator verified)</label>
                          <input id={`promote-people-${alert.id}`} type="number" min="0" max="1000000" step="1" value={promotionForm.people_affected} onChange={(event) => updatePromotionField("people_affected", event.target.value)} placeholder="Enter verified estimate" required disabled={busy} />
                        </div>

                        <div className="form-field form-field-full">
                          <label htmlFor={`promote-description-${alert.id}`}>Incident description</label>
                          <textarea id={`promote-description-${alert.id}`} rows={3} minLength={10} maxLength={1000} value={promotionForm.description} onChange={(event) => updatePromotionField("description", event.target.value)} required disabled={busy} />
                        </div>

                        <fieldset className="form-field form-field-full alert-help-fieldset">
                          <legend>Help required — select at least one</legend>
                          <div className="alert-help-options">
                            {["rescue", "medical", "evacuation", "shelter", "food", "water", "firefighting", "other"].map((value) => (
                              <label key={value} className="alert-help-option">
                                <input
                                  type="checkbox"
                                  checked={promotionForm.help_needed.includes(value)}
                                  onChange={(event) => togglePromotionHelp(value, event.target.checked)}
                                  disabled={busy}
                                />
                                <span>{labelize(value)}</span>
                              </label>
                            ))}
                          </div>
                        </fieldset>

                        <div className="form-field">
                          <label htmlFor={`promote-latitude-${alert.id}`}>Latitude (optional)</label>
                          <input id={`promote-latitude-${alert.id}`} type="number" min="-90" max="90" step="any" value={promotionForm.latitude} onChange={(event) => updatePromotionField("latitude", event.target.value)} disabled={busy} />
                        </div>
                        <div className="form-field">
                          <label htmlFor={`promote-longitude-${alert.id}`}>Longitude (optional)</label>
                          <input id={`promote-longitude-${alert.id}`} type="number" min="-180" max="180" step="any" value={promotionForm.longitude} onChange={(event) => updatePromotionField("longitude", event.target.value)} disabled={busy} />
                        </div>
                      </div>

                      {promotionError && <div className="field-error alert-promotion-error">{promotionError}</div>}
                      <div className="notice-box">
                        <Icon name="shield" size={14} />
                        <div>
                          <strong>Human verification required</strong>
                          <p>People affected and help-needed fields are operator inputs. Promotion creates an open incident with the existing prototype severity score; it does not approve a resource plan or dispatch anything.</p>
                        </div>
                      </div>
                      <div className="page-hero-actions">
                        <button type="submit" className="btn btn-primary" disabled={busy}>
                          <Icon name="checkCircle" size={14} />
                          <span>{busy ? "Creating incident..." : "Confirm & create incident"}</span>
                        </button>
                      </div>
                    </form>
                  )}

                  {assessment && <AssessmentPanel assessment={assessment} />}
                  {assessmentHistory[alert.id]?.length > 0 && (
                    <div className="alert-history-list">
                      <strong>Saved assessment runs</strong>
                      {assessmentHistory[alert.id].map((entry) => (
                        <button
                          type="button"
                          key={entry.id}
                          className="btn btn-secondary btn-xs"
                          onClick={() => setAssessments((current) => ({ ...current, [alert.id]: entry }))}
                        >
                          <span>#{entry.id} · {labelize(entry.review_priority)} · {formatRelative(entry.generated_at)}</span>
                        </button>
                      ))}
                    </div>
                  )}
                </article>
              );
            })}
          </div>
        )}
      </section>

      {disclaimer && <p className="alert-disclaimer">{disclaimer}</p>}
    </div>
  );
}
