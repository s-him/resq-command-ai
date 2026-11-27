import React, { useEffect, useState } from "react";
import { useData } from "../../context/DataContext";
import { useToast } from "../../context/ToastContext";
import { navigate } from "../../hooks/useHashRoute";
import { ApiError, describeError } from "../../services/apiClient";
import { createIncident } from "../../services/incidentService";
import { HAZARD_TYPES, HELP_TYPES, VULNERABLE_GROUPS } from "../../utils/constants";
import { incidentCode, labelize, toLocalInputValue } from "../../utils/format";
import Icon from "../common/Icon";
import Modal from "../common/Modal";

/**
 * Sample presets for quick professor demonstrations.
 * Clicking a preset only fills the form inputs; the operator still submits
 * the form to POST /api/incidents on the real FastAPI backend.
 */
const DEMO_PRESETS = {
  high: {
    hazard_type: "building_collapse",
    location: "Sector 9, Lake View Apartments",
    people_affected: "120",
    help_needed: ["rescue", "medical", "shelter"],
    vulnerable_groups: ["children", "disabled"],
    description:
      "Partial collapse of a four-storey residential wing following structural failure; residents reported trapped on the ground floor requiring urgent urban search and medical triage.",
    latitude: "12.9716",
    longitude: "77.5946",
  },
  low: {
    hazard_type: "flood",
    location: "Ward 3, Market Lane",
    people_affected: "8",
    help_needed: ["water", "food"],
    vulnerable_groups: [],
    description:
      "Localized street waterlogging near the low-lying market lane; eight residents in ground-floor shops need clean drinking water and dry ration packets.",
    latitude: "13.0827",
    longitude: "80.2707",
  },
};

function emptyForm() {
  return {
    hazard_type: "flood",
    location: "",
    people_affected: "25",
    reported_at: toLocalInputValue(),
    event_at: "",
    help_needed: ["medical"],
    vulnerable_groups: [],
    description: "",
    latitude: "",
    longitude: "",
    hazard_magnitude: "",
    hazard_magnitude_unit: "",
    provider_alert_level: "none",
  };
}

export default function IncidentFormModal({ open, initialPreset = null, onClose }) {
  const { refreshAll } = useData();
  const toast = useToast();

  const [form, setForm] = useState(emptyForm);
  const [submitting, setSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [fieldErrors, setFieldErrors] = useState({});

  useEffect(() => {
    if (!open) return;
    setErrorMessage("");
    setFieldErrors({});
    if (initialPreset && DEMO_PRESETS[initialPreset]) {
      setForm({
        ...emptyForm(),
        ...DEMO_PRESETS[initialPreset],
        reported_at: toLocalInputValue(),
      });
    } else {
      setForm(emptyForm());
    }
  }, [open, initialPreset]);

  function applyPreset(key) {
    const preset = DEMO_PRESETS[key];
    if (!preset) return;
    setErrorMessage("");
    setFieldErrors({});
    setForm({
      ...emptyForm(),
      ...preset,
      reported_at: toLocalInputValue(),
    });
  }

  function updateField(name, value) {
    setForm((prev) => ({ ...prev, [name]: value }));
    setFieldErrors((prev) => ({ ...prev, [name]: undefined }));
  }

  function toggleHelp(type) {
    setForm((prev) => {
      const exists = prev.help_needed.includes(type);
      const next = exists
        ? prev.help_needed.filter((t) => t !== type)
        : [...prev.help_needed, type];
      return { ...prev, help_needed: next };
    });
    setFieldErrors((prev) => ({ ...prev, help_needed: undefined }));
  }

  function toggleVulnerableGroup(group) {
    setForm((prev) => {
      const exists = prev.vulnerable_groups.includes(group);
      const next = exists
        ? prev.vulnerable_groups.filter((item) => item !== group)
        : [...prev.vulnerable_groups, group];
      return { ...prev, vulnerable_groups: next };
    });
  }

  function validateLocally() {
    const errs = {};
    if (form.location.trim().length < 2) {
      errs.location = "Location must be at least 2 characters.";
    }
    if (form.description.trim().length < 10) {
      errs.description = "Description must be at least 10 characters.";
    }
    const people = Number(form.people_affected);
    if (!Number.isInteger(people) || people < 0 || people > 1_000_000) {
      errs.people_affected = "Enter a whole number between 0 and 1,000,000.";
    }
    if (form.help_needed.length === 0) {
      errs.help_needed = "Select at least one requested assistance category.";
    }
    const hasMagnitude = form.hazard_magnitude.trim() !== "";
    const hasMagnitudeUnit = form.hazard_magnitude_unit.trim() !== "";
    if (hasMagnitude !== hasMagnitudeUnit) {
      errs.hazard_magnitude = "Provide both a hazard measurement and its unit, or leave both blank.";
      errs.hazard_magnitude_unit = "Provide both a hazard measurement and its unit, or leave both blank.";
    } else if (hasMagnitude && (!Number.isFinite(Number(form.hazard_magnitude)) || Number(form.hazard_magnitude) < 0)) {
      errs.hazard_magnitude = "Enter a non-negative numeric measurement.";
    }
    const hasLat = form.latitude.trim() !== "";
    const hasLng = form.longitude.trim() !== "";
    if (hasLat !== hasLng) {
      errs.latitude = "Provide both latitude and longitude, or leave both blank.";
      errs.longitude = "Provide both latitude and longitude, or leave both blank.";
    } else if (hasLat && hasLng) {
      const lat = Number(form.latitude);
      const lng = Number(form.longitude);
      if (Number.isNaN(lat) || lat < -90 || lat > 90) {
        errs.latitude = "Latitude must be between -90 and 90.";
      }
      if (Number.isNaN(lng) || lng < -180 || lng > 180) {
        errs.longitude = "Longitude must be between -180 and 180.";
      }
    }
    return errs;
  }

  async function handleSubmit(event) {
    event.preventDefault();
    if (submitting) return;

    setErrorMessage("");
    const localErrors = validateLocally();
    if (Object.keys(localErrors).length > 0) {
      setFieldErrors(localErrors);
      setErrorMessage("Please fix the highlighted fields before submitting.");
      return;
    }

    setSubmitting(true);
    try {
      const payload = {
        hazard_type: form.hazard_type,
        description: form.description.trim(),
        location: form.location.trim(),
        reported_at: new Date(form.reported_at).toISOString(),
        people_affected: Number(form.people_affected),
        help_needed: form.help_needed,
        vulnerable_groups: form.vulnerable_groups,
      };
      if (form.event_at.trim() !== "") {
        payload.event_at = new Date(form.event_at).toISOString();
      }
      if (form.latitude.trim() !== "" && form.longitude.trim() !== "") {
        payload.latitude = Number(form.latitude);
        payload.longitude = Number(form.longitude);
      }
      if (form.hazard_magnitude.trim() !== "" && form.hazard_magnitude_unit.trim() !== "") {
        payload.hazard_magnitude = Number(form.hazard_magnitude);
        payload.hazard_magnitude_unit = form.hazard_magnitude_unit.trim();
      }
      if (form.provider_alert_level !== "none") {
        payload.provider_alert_level = form.provider_alert_level;
      }

      const created = await createIncident(payload);
      await refreshAll();
      toast({
        type: "success",
        title: `${incidentCode(created.id)} recorded`,
        message: `Severity assessed as ${created.severity.level} (${created.severity.score}/${created.severity.max_score}).`,
      });
      onClose?.();
      navigate(`#/incidents/${created.id}`);
    } catch (error) {
      if (error instanceof ApiError && error.kind === "validation") {
        setFieldErrors(error.fieldErrors || {});
      }
      setErrorMessage(describeError(error));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={submitting ? undefined : onClose}
      size="lg"
      title="Report Disaster Incident"
      subtitle="Submit a manual or sample incident report for six-factor prototype severity evaluation."
      footer={
        <>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={onClose}
            disabled={submitting}
          >
            Cancel
          </button>
          <button
            type="submit"
            form="create-incident-form"
            className="btn btn-primary"
            disabled={submitting}
          >
            <Icon name="plus" size={16} />
            <span>{submitting ? "Submitting to backend..." : "Submit Incident Report"}</span>
          </button>
        </>
      }
    >
      <div className="preset-bar">
        <span className="preset-label">Quick-fill academic sample data:</span>
        <button
          type="button"
          className="btn btn-secondary btn-xs"
          onClick={() => applyPreset("high")}
          disabled={submitting}
        >
          Sample Building Collapse (Critical / High)
        </button>
        <button
          type="button"
          className="btn btn-secondary btn-xs"
          onClick={() => applyPreset("low")}
          disabled={submitting}
        >
          Sample Market Lane Flood (Low)
        </button>
      </div>

      {errorMessage && (
        <div className="error-panel" role="alert" style={{ marginBottom: 14 }}>
          <div className="error-panel-main">
            <Icon name="alertCircle" size={18} className="error-panel-icon" />
            <div>
              <h3 className="error-panel-title">Submission failed</h3>
              <p className="error-panel-msg">{errorMessage}</p>
            </div>
          </div>
        </div>
      )}

      <form id="create-incident-form" onSubmit={handleSubmit} className="form-grid" noValidate>
        <div className="form-field">
          <label htmlFor="inc-hazard">
            Hazard Type <span className="req-star">*</span>
          </label>
          <select
            id="inc-hazard"
            value={form.hazard_type}
            onChange={(e) => updateField("hazard_type", e.target.value)}
            disabled={submitting}
          >
            {HAZARD_TYPES.map((type) => (
              <option key={type} value={type}>
                {labelize(type)}
              </option>
            ))}
          </select>
          <span className="field-hint">Allowed backend HazardType enum value.</span>
          {fieldErrors.hazard_type && (
            <span className="field-error">{fieldErrors.hazard_type}</span>
          )}
        </div>

        <div className="form-field">
          <label htmlFor="inc-people">
            Estimated People Affected <span className="req-star">*</span>
          </label>
          <input
            id="inc-people"
            type="number"
            min="0"
            max="1000000"
            step="1"
            required
            placeholder="e.g. 120"
            value={form.people_affected}
            onChange={(e) => updateField("people_affected", e.target.value)}
            disabled={submitting}
          />
          <span className="field-hint">Whole number from 0 to 1,000,000 (contributes 0–35 prototype points).</span>
          {fieldErrors.people_affected && (
            <span className="field-error">{fieldErrors.people_affected}</span>
          )}
        </div>

        <div className="form-field">
          <label htmlFor="inc-location">
            Location <span className="req-star">*</span>
          </label>
          <input
            id="inc-location"
            type="text"
            required
            minLength={2}
            maxLength={200}
            placeholder="e.g. Sector 9, Lake View Apartments"
            value={form.location}
            onChange={(e) => updateField("location", e.target.value)}
            disabled={submitting}
          />
          <span className="field-hint">2–200 characters describing the reported sector or ward.</span>
          {fieldErrors.location && <span className="field-error">{fieldErrors.location}</span>}
        </div>

        <div className="form-field">
          <label htmlFor="inc-event">Event Time (optional)</label>
          <input
            id="inc-event"
            type="datetime-local"
            value={form.event_at}
            onChange={(e) => updateField("event_at", e.target.value)}
            disabled={submitting}
          />
          <span className="field-hint">When the event happened, if known. The report time remains separate.</span>
          {fieldErrors.event_at && <span className="field-error">{fieldErrors.event_at}</span>}
        </div>

        <div className="form-field">
          <label htmlFor="inc-reported">
            Reported Time <span className="req-star">*</span>
          </label>
          <input
            id="inc-reported"
            type="datetime-local"
            required
            value={form.reported_at}
            onChange={(e) => updateField("reported_at", e.target.value)}
            disabled={submitting}
          />
          <span className="field-hint">Cannot be in the future; older reports break priority ties.</span>
          {fieldErrors.reported_at && (
            <span className="field-error">{fieldErrors.reported_at}</span>
          )}
        </div>

        <div className="form-field">
          <label htmlFor="inc-magnitude">Hazard Measurement (optional)</label>
          <input
            id="inc-magnitude"
            type="number"
            min="0"
            step="any"
            placeholder="e.g. 6.4"
            value={form.hazard_magnitude}
            onChange={(e) => updateField("hazard_magnitude", e.target.value)}
            disabled={submitting}
          />
          <span className="field-hint">Use a value reported by the source, not a guess.</span>
          {fieldErrors.hazard_magnitude && <span className="field-error">{fieldErrors.hazard_magnitude}</span>}
        </div>

        <div className="form-field">
          <label htmlFor="inc-magnitude-unit">Measurement Unit</label>
          <select
            id="inc-magnitude-unit"
            value={form.hazard_magnitude_unit}
            onChange={(e) => updateField("hazard_magnitude_unit", e.target.value)}
            disabled={submitting}
          >
            <option value="">Select unit</option>
            <option value="magnitude">Magnitude (earthquake)</option>
            <option value="category">Category (cyclone)</option>
            <option value="km/h">Wind speed (km/h)</option>
            <option value="knots">Wind speed (knots)</option>
            <option value="m/s">Wind speed (m/s)</option>
            <option value="mph">Wind speed (mph)</option>
            <option value="m">Flood-water depth (metres)</option>
            <option value="cm">Flood-water depth (centimetres)</option>
            <option value="mm">Flood-water depth (millimetres)</option>
            <option value="ft">Flood-water depth (feet)</option>
          </select>
          <span className="field-hint">Earthquake magnitude, cyclone wind/category, or flood-water depth. Unsupported units are preserved without invented points.</span>
          {fieldErrors.hazard_magnitude_unit && <span className="field-error">{fieldErrors.hazard_magnitude_unit}</span>}
        </div>

        <div className="form-field">
          <label htmlFor="inc-provider-alert">Provider Alert Level (optional)</label>
          <select
            id="inc-provider-alert"
            value={form.provider_alert_level}
            onChange={(e) => updateField("provider_alert_level", e.target.value)}
            disabled={submitting}
          >
            <option value="none">Not supplied</option>
            <option value="green">Green</option>
            <option value="orange">Orange</option>
            <option value="red">Red</option>
          </select>
          <span className="field-hint">Only use an alert level present in the source report.</span>
        </div>

        <div className="form-field form-field-full">
          <label>
            Requested Assistance <span className="req-star">*</span>
          </label>
          <div className="chip-selector" role="group" aria-label="Requested assistance types">
            {HELP_TYPES.map((type) => {
              const selected = form.help_needed.includes(type);
              const isImmediate = ["rescue", "medical", "evacuation", "firefighting"].includes(
                type
              );
              return (
                <button
                  key={type}
                  type="button"
                  className={`chip-option ${selected ? "is-selected" : ""}`}
                  onClick={() => toggleHelp(type)}
                  disabled={submitting}
                  aria-pressed={selected}
                >
                  <span>{labelize(type)}</span>
                  {isImmediate && <span className="chip-tag">Immediate</span>}
                </button>
              );
            })}
          </div>
          <span className="field-hint">
            Select at least one. Immediate life-safety assistance types contribute 15–20 prototype
            points.
          </span>
          {fieldErrors.help_needed && (
            <span className="field-error">{fieldErrors.help_needed}</span>
          )}
        </div>

        <div className="form-field form-field-full">
          <label>Vulnerable Groups at Risk (optional)</label>
          <div className="chip-selector" role="group" aria-label="Vulnerable groups at risk">
            {VULNERABLE_GROUPS.map((group) => {
              const selected = form.vulnerable_groups.includes(group);
              return (
                <button
                  key={group}
                  type="button"
                  className={"chip-option " + (selected ? "is-selected" : "")}
                  onClick={() => toggleVulnerableGroup(group)}
                  disabled={submitting}
                  aria-pressed={selected}
                >
                  {labelize(group)}
                </button>
              );
            })}
          </div>
          <span className="field-hint">
            Select only groups confirmed in the report. Explicit selections take priority over description keywords and add up to 5 severity points.
          </span>
        </div>

        <div className="form-field form-field-full">
          <label htmlFor="inc-desc">
            Incident Description <span className="req-star">*</span>
          </label>
          <textarea
            id="inc-desc"
            rows={3}
            required
            minLength={10}
            maxLength={1000}
            placeholder="Describe the reported situation, structural impact, and assistance needed (10–1000 characters)..."
            value={form.description}
            onChange={(e) => updateField("description", e.target.value)}
            disabled={submitting}
          />
          <span className="field-hint">
            {form.description.trim().length}/1000 characters (minimum 10).
          </span>
          {fieldErrors.description && (
            <span className="field-error">{fieldErrors.description}</span>
          )}
        </div>

        <div className="form-field">
          <label htmlFor="inc-lat">Latitude (optional, reported/sample)</label>
          <input
            id="inc-lat"
            type="number"
            step="any"
            min="-90"
            max="90"
            placeholder="e.g. 12.9716"
            value={form.latitude}
            onChange={(e) => updateField("latitude", e.target.value)}
            disabled={submitting}
          />
          <span className="field-hint">Between -90 and 90. Pair with longitude.</span>
          {fieldErrors.latitude && <span className="field-error">{fieldErrors.latitude}</span>}
        </div>

        <div className="form-field">
          <label htmlFor="inc-lng">Longitude (optional, reported/sample)</label>
          <input
            id="inc-lng"
            type="number"
            step="any"
            min="-180"
            max="180"
            placeholder="e.g. 77.5946"
            value={form.longitude}
            onChange={(e) => updateField("longitude", e.target.value)}
            disabled={submitting}
          />
          <span className="field-hint">Between -180 and 180. Pair with latitude.</span>
          {fieldErrors.longitude && <span className="field-error">{fieldErrors.longitude}</span>}
        </div>
      </form>
    </Modal>
  );
}

