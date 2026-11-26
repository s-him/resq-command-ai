import React, { useEffect, useState } from "react";
import Icon from "../common/Icon";
import { describeError } from "../../services/apiClient";
import { getDispatchSettings, updateDispatchSettings } from "../../services/dispatchService";

/** Operator controls for the persisted MANUAL/AUTO simulation policy. */
export default function DispatchSettingsPanel({ onUpdated, toast }) {
  const [settings, setSettings] = useState(null);
  const [draft, setDraft] = useState({ mode: "manual", minimum_severity: "High" });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    try {
      const current = await getDispatchSettings();
      setSettings(current);
      setDraft({
        mode: current.mode,
        minimum_severity: current.minimum_severity,
      });
      setError("");
    } catch (err) {
      setError(describeError(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function save(patch) {
    if (saving) return;
    setSaving(true);
    try {
      const updated = await updateDispatchSettings(patch);
      setSettings(updated);
      setDraft({
        mode: updated.mode,
        minimum_severity: updated.minimum_severity,
      });
      setError("");
      toast?.({
        type: "success",
        title: "Dispatch settings saved",
        message: updated.mode === "auto" && !updated.paused
          ? "AUTO simulation is active for eligible open incidents."
          : "Automatic assignments are not being started.",
      });
      await onUpdated?.();
    } catch (err) {
      setError(describeError(err));
      toast?.({
        type: "error",
        title: "Could not update dispatch settings",
        message: describeError(err),
      });
    } finally {
      setSaving(false);
    }
  }

  const paused = Boolean(settings?.paused);
  const isDirty = Boolean(settings) && (
    draft.mode !== settings.mode ||
    draft.minimum_severity !== settings.minimum_severity
  );

  return (
    <section className="surface-card dispatch-settings-panel">
      <div className="panel-header">
        <div>
          <h3 className="section-title">Dispatch Mode &amp; Emergency Control</h3>
          <p className="section-subtitle">
            MANUAL is the safe default. AUTO creates simulated assignments and virtual reservations only.
          </p>
        </div>
        <span className={"dispatch-mode-pill dispatch-mode-" + (settings?.mode || "manual")}>
          {settings?.mode?.toUpperCase() || "LOADING"}
        </span>
      </div>

      {error && <div className="inline-error" role="alert">{error}</div>}

      <div className="dispatch-settings-grid">
        <div className="form-field">
          <label htmlFor="dispatch-mode">Dispatch mode</label>
          <select
            id="dispatch-mode"
            value={draft.mode}
            onChange={(event) => setDraft((current) => ({ ...current, mode: event.target.value }))}
            disabled={loading || saving}
          >
            <option value="manual">MANUAL — operator approval</option>
            <option value="auto">AUTO — simulated assignments</option>
          </select>
        </div>
        <div className="form-field">
          <label htmlFor="dispatch-threshold">Minimum severity for AUTO</label>
          <select
            id="dispatch-threshold"
            value={draft.minimum_severity}
            onChange={(event) => setDraft((current) => ({ ...current, minimum_severity: event.target.value }))}
            disabled={loading || saving}
          >
            <option value="High">High or Critical</option>
            <option value="Critical">Critical only</option>
          </select>
        </div>
        <div className="dispatch-settings-actions">
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => save({ mode: draft.mode, minimum_severity: draft.minimum_severity, paused: paused })}
            disabled={loading || saving || !isDirty}
          >
            <Icon name="checkCircle" size={15} />
            <span>{saving ? "Saving…" : "Save Dispatch Settings"}</span>
          </button>
          <button
            type="button"
            className={paused ? "btn btn-primary" : "btn btn-danger"}
            onClick={() => save({ paused: !paused })}
            disabled={loading || saving || !settings}
            aria-pressed={paused}
          >
            <Icon name={paused ? "arrowRight" : "xCircle"} size={15} />
            <span>{paused ? "Resume AUTO Dispatch" : "Pause All AUTO Dispatch"}</span>
          </button>
        </div>
      </div>

      <div className={paused ? "dispatch-kill-state is-paused" : "dispatch-kill-state"} role="status">
        <Icon name={paused ? "alertCircle" : "shield"} size={16} />
        <span>
          {paused
            ? "Emergency pause is active. New automatic dispatches and shortfall retries are blocked."
            : settings?.mode === "auto"
              ? "AUTO is enabled at the " + settings.minimum_severity + " threshold."
              : "MANUAL mode is active. Every recommendation still waits for operator approval."}
        </span>
      </div>
    </section>
  );
}
