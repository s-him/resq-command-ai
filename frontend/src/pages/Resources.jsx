import React, { useMemo, useState } from "react";
import { CodeBadge, StatusBadge } from "../components/common/Badge";
import EmptyState from "../components/common/EmptyState";
import ErrorState from "../components/common/ErrorState";
import Icon from "../components/common/Icon";
import Modal from "../components/common/Modal";
import { SkeletonTable } from "../components/common/Skeleton";
import { useData } from "../context/DataContext";
import { useToast } from "../context/ToastContext";
import { ApiError, describeError } from "../services/apiClient";
import { createResource, getResourceHistory, updateResource } from "../services/resourceService";
import {
  AVAILABILITY_STATUSES,
  RESOURCE_ICONS,
  RESOURCE_TYPES,
} from "../utils/constants";
import {
  formatDateTime,
  formatNumber,
  labelize,
  resourceCode,
} from "../utils/format";

const RESOURCE_PRESETS = [
  {
    label: "Ambulance Unit (3)",
    resource_type: "ambulance",
    name: "City Hospital Ambulance Unit A",
    quantity_available: "3",
    location: "Central Medical Depot, Ward 4",
    availability_status: "available",
  },
  {
    label: "Rescue Team (4)",
    resource_type: "rescue_team",
    name: "Urban Search & River Rescue Squad",
    quantity_available: "4",
    location: "North Command Station, Sector 2",
    availability_status: "available",
  },
  {
    label: "Emergency Shelter (150)",
    resource_type: "shelter",
    name: "Community Hall Relief Shelter",
    quantity_available: "150",
    location: "Ward 12 High School Ground",
    availability_status: "available",
  },
  {
    label: "Water & Ration Kits (250)",
    resource_type: "supply",
    name: "Potable Water & Dry Ration Packs",
    quantity_available: "250",
    location: "Municipal Relief Warehouse",
    availability_status: "available",
  },
];

function emptyResourceForm() {
  return {
    resource_type: "ambulance",
    name: "",
    quantity_available: "3",
    location: "",
    availability_status: "available",
    latitude: "",
    longitude: "",
    note: "",
  };
}

export default function Resources() {
  const { resources, refreshing, refreshAll } = useData();
  const toast = useToast();

  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");

  const [modalOpen, setModalOpen] = useState(false);
  const [form, setForm] = useState(emptyResourceForm);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState("");
  const [fieldErrors, setFieldErrors] = useState({});
  const [editingResourceId, setEditingResourceId] = useState(null);
  const [resourceHistory, setResourceHistory] = useState({});
  const [historyLoadingId, setHistoryLoadingId] = useState(null);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return resources.data.filter((res) => {
      if (typeFilter !== "all" && res.resource_type !== typeFilter) return false;
      if (statusFilter !== "all" && res.availability_status !== statusFilter) return false;
      if (!q) return true;
      return (
        resourceCode(res.id).toLowerCase().includes(q) ||
        res.name.toLowerCase().includes(q) ||
        res.resource_type.toLowerCase().includes(q) ||
        res.location.toLowerCase().includes(q)
      );
    });
  }, [resources.data, search, typeFilter, statusFilter]);

  const categorySummary = useMemo(() => {
    return RESOURCE_TYPES.map((type) => {
      const matching = resources.data.filter((r) => r.resource_type === type);
      const availUnits = matching
        .filter((r) => r.availability_status === "available")
        .reduce((sum, r) => sum + (r.simulation_remaining_quantity ?? r.quantity_available ?? 0), 0);
      return {
        type,
        poolCount: matching.length,
        availUnits,
      };
    });
  }, [resources.data]);

  function openAddModal(preset = null) {
    setEditingResourceId(null);
    setFormError("");
    setFieldErrors({});
    if (preset) {
      setForm({
        ...emptyResourceForm(),
        resource_type: preset.resource_type,
        name: preset.name,
        quantity_available: String(preset.quantity_available),
        location: preset.location,
        availability_status: preset.availability_status,
        latitude: preset.latitude || "",
        longitude: preset.longitude || "",
      });
    } else {
      setForm(emptyResourceForm());
    }
    setModalOpen(true);
  }

  function openEditModal(resource) {
    setEditingResourceId(resource.id);
    setFormError("");
    setFieldErrors({});
    setForm({
      resource_type: resource.resource_type,
      name: resource.name,
      quantity_available: String(resource.quantity_available),
      location: resource.location,
      availability_status: resource.availability_status,
      latitude: resource.latitude === null ? "" : String(resource.latitude),
      longitude: resource.longitude === null ? "" : String(resource.longitude),
      note: "",
    });
    setModalOpen(true);
  }

  async function toggleResourceHistory(resource) {
    if (resourceHistory[resource.id]) {
      setResourceHistory((current) => {
        const next = { ...current };
        delete next[resource.id];
        return next;
      });
      return;
    }
    if (historyLoadingId !== null) return;
    setHistoryLoadingId(resource.id);
    try {
      const result = await getResourceHistory(resource.id);
      setResourceHistory((current) => ({ ...current, [resource.id]: result.entries }));
    } catch (err) {
      toast({
        type: "error",
        title: "Could not load resource history",
        message: describeError(err),
      });
    } finally {
      setHistoryLoadingId(null);
    }
  }

  async function handleCreateResource(event) {
    event.preventDefault();
    if (submitting) return;
    setFormError("");

    const errs = {};
    if (form.name.trim().length < 2) errs.name = "Name must be at least 2 characters.";
    if (form.location.trim().length < 2) errs.location = "Location must be at least 2 characters.";
    const qty = Number(form.quantity_available);
    if (!Number.isInteger(qty) || qty < 0 || qty > 1_000_000) {
      errs.quantity_available = "Quantity must be a whole number from 0 to 1,000,000.";
    }
    const hasLatitude = form.latitude.trim() !== "";
    const hasLongitude = form.longitude.trim() !== "";
    if (hasLatitude !== hasLongitude) {
      errs.latitude = "Provide both latitude and longitude, or leave both empty.";
      errs.longitude = "Provide both latitude and longitude, or leave both empty.";
    }
    if (hasLatitude && (!Number.isFinite(Number(form.latitude)) || Number(form.latitude) < -90 || Number(form.latitude) > 90)) {
      errs.latitude = "Latitude must be between -90 and 90.";
    }
    if (hasLongitude && (!Number.isFinite(Number(form.longitude)) || Number(form.longitude) < -180 || Number(form.longitude) > 180)) {
      errs.longitude = "Longitude must be between -180 and 180.";
    }
    if (Object.keys(errs).length > 0) {
      setFieldErrors(errs);
      setFormError("Please fix the highlighted fields.");
      return;
    }

    setSubmitting(true);
    try {
      const payload = {
        resource_type: form.resource_type,
        name: form.name.trim(),
        quantity_available: qty,
        location: form.location.trim(),
        availability_status: form.availability_status,
        latitude: hasLatitude ? Number(form.latitude) : null,
        longitude: hasLongitude ? Number(form.longitude) : null,
      };

      if (editingResourceId !== null) {
        const updated = await updateResource(editingResourceId, {
          ...payload,
          note: form.note.trim() || null,
        });
        await refreshAll();
        toast({
          type: "success",
          title: `${resourceCode(updated.id)} updated`,
          message: `${updated.name} · physical stock ${updated.quantity_available} · ${updated.availability_status}.`,
        });
      } else {
        const created = await createResource(payload);
        await refreshAll();
        toast({
          type: "success",
          title: `${resourceCode(created.id)} registered`,
          message: `${created.name} (${created.quantity_available} unit(s), ${created.availability_status}).`,
        });
      }
      setModalOpen(false);
      setEditingResourceId(null);
        resource_type: form.resource_type,
        name: form.name.trim(),
        quantity_available: qty,
        location: form.location.trim(),
        availability_status: form.availability_status,
        latitude: hasLatitude ? Number(form.latitude) : null,
        longitude: hasLongitude ? Number(form.longitude) : null,
      });
      setModalOpen(false);
    } catch (err) {
      if (err instanceof ApiError && err.kind === "validation") {
        setFieldErrors(err.fieldErrors || {});
      }
      setFormError(describeError(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="page-stack">
      <section className="page-hero">
        <div>
          <h2 className="page-heading">Resource Inventory</h2>
          <p className="page-subheading">
            Register and monitor relief assets. Only resources marked available with a positive
            quantity are matched by the recommendation engine.
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
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => openAddModal()}
          >
            <Icon name="plus" size={16} />
            <span>Add Resource</span>
          </button>
        </div>
      </section>

      {/* Category summary strip */}
      <section className="category-strip" aria-label="Resource categories">
        {categorySummary.map((cat) => (
          <button
            key={cat.type}
            type="button"
            className={`surface-card category-tile ${typeFilter === cat.type ? "is-selected" : ""
              }`}
            onClick={() =>
              setTypeFilter((current) => (current === cat.type ? "all" : cat.type))
            }
          >
            <div className="category-tile-top">
              <span className="hazard-icon-chip">
                <Icon name={RESOURCE_ICONS[cat.type] || "package"} size={16} />
              </span>
              <span className="category-tile-name">{labelize(cat.type)}</span>
            </div>
            <div className="category-tile-num tabular">{formatNumber(cat.availUnits)}</div>
            <div className="category-tile-sub tabular">
              simulation-unreserved units · {cat.poolCount} pool(s)
            </div>
          </button>
        ))}
      </section>

      {/* Resource Cards + Detailed Inventory Table */}
      <section className="surface-card">
        <div className="panel-header">
          <div>
            <h3 className="section-title">Registered Resource Pools</h3>
            <p className="section-subtitle">
              Inventory quantities are preserved across recommendations and operator approvals.
            </p>
          </div>
        </div>

        <div className="toolbar-row">
          <div className="search-box">
            <Icon name="search" size={16} className="search-icon" />
            <input
              type="search"
              placeholder="Search resources by ID, name, category, or depot location..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              aria-label="Search resources"
            />
          </div>

          <div className="filter-group">
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              aria-label="Filter by resource category"
            >
              <option value="all">All categories</option>
              {RESOURCE_TYPES.map((t) => (
                <option key={t} value={t}>
                  {labelize(t)}
                </option>
              ))}
            </select>

            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              aria-label="Filter by availability status"
            >
              <option value="all">All statuses</option>
              {AVAILABILITY_STATUSES.map((st) => (
                <option key={st} value={st}>
                  {labelize(st)}
                </option>
              ))}
            </select>
          </div>
        </div>

        {resources.error ? (
          <ErrorState
            title="Could not load resource inventory"
            error={resources.error}
            onRetry={refreshAll}
          />
        ) : resources.loading && resources.data.length === 0 ? (
          <SkeletonTable rows={4} />
        ) : resources.data.length === 0 ? (
          <EmptyState
            icon="package"
            title="No resources registered yet"
            description="Add ambulances, rescue teams, shelters, or supplies so the recommendation engine can match them against open incidents."
            actionLabel="Add Sample Ambulance Resource"
            onAction={() => openAddModal(RESOURCE_PRESETS[0])}
            secondaryActionLabel="Open Blank Resource Form"
            onSecondaryAction={() => openAddModal()}
          />
        ) : filtered.length === 0 ? (
          <EmptyState
            icon="search"
            title="No resources match your filters"
            description="Clear the active search or category/status filters to view all registered resources."
            secondaryActionLabel="Reset Filters"
            onSecondaryAction={() => {
              setSearch("");
              setTypeFilter("all");
              setStatusFilter("all");
            }}
          />
        ) : (
          <>
            <div className="resource-cards-grid">
              {filtered.map((res) => (
                <article key={`card-${res.id}`} className="resource-card">
                  <div className="resource-card-top">
                    <div className="cell-hazard">
                      <span className="hazard-icon-chip">
                        <Icon name={RESOURCE_ICONS[res.resource_type] || "package"} size={16} />
                      </span>
                      <div>
                        <div className="resource-card-title">{res.name}</div>
                        <div className="cell-sub">{labelize(res.resource_type)}</div>
                      </div>
                    </div>
                    <CodeBadge>{resourceCode(res.id)}</CodeBadge>
                  </div>

                  <div className="resource-card-qty-row">
                    <div>
                      <span className="resource-qty-label">Physical Quantity</span>
                      <div className="resource-qty-val tabular">
                        {formatNumber(res.quantity_available)}
                      </div>
                      <div className="cell-sub tabular">
                        Simulation reserved: {formatNumber(res.simulation_reserved_quantity || 0)}
                      </div>
                      <div className="cell-sub tabular">
                        Remaining for simulation: {formatNumber(res.simulation_remaining_quantity ?? res.quantity_available)}
                      </div>
                    </div>
                    <StatusBadge status={res.availability_status} />
                  </div>

                  <div className="resource-card-meta">
                    <Icon name="mapPin" size={14} />
                    <span>{res.location}</span>
                  </div>
                  <div className="resource-card-meta">
                    <Icon name="crosshair" size={14} />
                    <span>
                      {typeof res.latitude === "number" && typeof res.longitude === "number"
                        ? `${res.latitude.toFixed(4)}, ${res.longitude.toFixed(4)}`
                        : "Coordinates not registered"}
                    </span>
                  </div>
                  <div className="resource-card-actions">
                    <button type="button" className="btn btn-secondary btn-xs" onClick={() => openEditModal(res)}>
                      <span>Edit inventory</span>
                    </button>
                    <button type="button" className="btn btn-secondary btn-xs" onClick={() => toggleResourceHistory(res)} disabled={historyLoadingId !== null}>
                      <Icon name="history" size={13} />
                      <span>{historyLoadingId === res.id ? "Loading..." : resourceHistory[res.id] ? "Hide history" : "View history"}</span>
                    </button>
                  </div>
                  {resourceHistory[res.id] && (
                    <div className="resource-history-panel">
                      <strong>Inventory audit history</strong>
                      {resourceHistory[res.id].map((entry) => (
                        <div className="resource-history-entry" key={entry.id}>
                          <div className="resource-history-entry-head">
                            <span>{labelize(entry.action)}</span>
                            <time>{formatDateTime(entry.created_at)}</time>
                          </div>
                          {entry.note && <p>{entry.note}</p>}
                          <ul>
                            {Object.entries(entry.changes).map(([field, values]) => (
                              <li key={field}>
                                <strong>{labelize(field)}:</strong> {values.from === null ? "—" : String(values.from)} → {values.to === null ? "—" : String(values.to)}
                              </li>
                            ))}
                          </ul>
                        </div>
                      ))}
                    </div>
                  )}
                </article>
              ))}
            </div>

            <h4 className="rec-subhead" style={{ marginTop: 22 }}>
              Detailed Inventory Table
            </h4>
            <div className="table-scroll">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Resource ID</th>
                    <th>Name</th>
                    <th>Category</th>
                    <th>Location</th>
                    <th>Coordinates</th>
                    <th>Physical Quantity</th>
                    <th>Simulation Reserved</th>
                    <th>Simulation Remaining</th>
                    <th>Availability Status</th>
                    <th>Registered (UTC)</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((res) => (
                    <tr key={res.id}>
                      <td data-label="Resource ID">
                        <CodeBadge>{resourceCode(res.id)}</CodeBadge>
                      </td>
                      <td data-label="Name" className="font-medium">
                        {res.name}
                      </td>
                      <td data-label="Category">{labelize(res.resource_type)}</td>
                      <td data-label="Location">{res.location}</td>
                      <td data-label="Coordinates" className="tabular text-muted">
                        {typeof res.latitude === "number" && typeof res.longitude === "number"
                          ? `${res.latitude.toFixed(4)}, ${res.longitude.toFixed(4)}`
                          : "—"}
                      </td>
                      <td data-label="Physical Quantity" className="tabular font-medium">
                        {formatNumber(res.quantity_available)}
                      </td>
                      <td data-label="Simulation Reserved" className="tabular">
                        {formatNumber(res.simulation_reserved_quantity || 0)}
                      </td>
                      <td data-label="Simulation Remaining" className="tabular font-medium">
                        {formatNumber(res.simulation_remaining_quantity ?? res.quantity_available)}
                      </td>
                      <td data-label="Availability Status">
                        <StatusBadge status={res.availability_status} />
                      </td>
                      <td data-label="Registered (UTC)" className="tabular text-muted">
                        {formatDateTime(res.created_at)}
                      </td>
                      <td data-label="Actions">
                        <div className="resource-table-actions">
                          <button type="button" className="btn btn-secondary btn-xs" onClick={() => openEditModal(res)}>Edit</button>
                          <button type="button" className="btn btn-secondary btn-xs" onClick={() => toggleResourceHistory(res)} disabled={historyLoadingId !== null}>History</button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </section>

      <Modal
        open={modalOpen}
        onClose={submitting ? undefined : () => setModalOpen(false)}
        size="md"
        title={editingResourceId !== null ? "Edit Relief Resource" : "Register Relief Resource"}
        subtitle={editingResourceId !== null ? "Update physical inventory details. Active simulation reservations are protected." : "Adds a resource record to SQLite via POST /api/resources."}
        footer={
          <>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => setModalOpen(false)}
              disabled={submitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              form="add-resource-form"
              className="btn btn-primary"
              disabled={submitting}
            >
              <Icon name={editingResourceId !== null ? "checkCircle" : "plus"} size={16} />
              <span>{submitting ? "Saving..." : editingResourceId !== null ? "Update Resource" : "Save Resource"}</span>
            </button>
          </>
        }
      >
        {editingResourceId === null && <div className="preset-bar">
          <span className="preset-label">Quick-fill sample resource:</span>
          {RESOURCE_PRESETS.map((preset) => (
            <button
              key={preset.label}
              type="button"
              className="btn btn-secondary btn-xs"
              onClick={() =>
                setForm({
                  resource_type: preset.resource_type,
                  name: preset.name,
                  quantity_available: preset.quantity_available,
                  location: preset.location,
                  availability_status: preset.availability_status,
                })
              }
              disabled={submitting}
            >
              {preset.label}
            </button>
          ))}
        </div>}

        {formError && (
          <div className="error-panel" role="alert" style={{ marginBottom: 12 }}>
            <div className="error-panel-main">
              <Icon name="alertCircle" size={18} className="error-panel-icon" />
              <div>
                <h3 className="error-panel-title">Could not save resource</h3>
                <p className="error-panel-msg">{formError}</p>
              </div>
            </div>
          </div>
        )}

        <form
          id="add-resource-form"
          onSubmit={handleCreateResource}
          className="form-grid"
          noValidate
        >
          <div className="form-field">
            <label htmlFor="res-type">
              Resource Category <span className="req-star">*</span>
            </label>
            <select
              id="res-type"
              value={form.resource_type}
              onChange={(e) => setForm((f) => ({ ...f, resource_type: e.target.value }))}
              disabled={submitting}
            >
              {RESOURCE_TYPES.map((type) => (
                <option key={type} value={type}>
                  {labelize(type)}
                </option>
              ))}
            </select>
            {fieldErrors.resource_type && (
              <span className="field-error">{fieldErrors.resource_type}</span>
            )}
          </div>

          <div className="form-field">
            <label htmlFor="res-qty">
              Quantity Available <span className="req-star">*</span>
            </label>
            <input
              id="res-qty"
              type="number"
              min="0"
              max="1000000"
              step="1"
              required
              value={form.quantity_available}
              onChange={(e) =>
                setForm((f) => ({ ...f, quantity_available: e.target.value }))
              }
              disabled={submitting}
            />
            <span className="field-hint">Non-negative integer (0 to 1,000,000).</span>
            {fieldErrors.quantity_available && (
              <span className="field-error">{fieldErrors.quantity_available}</span>
            )}
          </div>

          <div className="form-field form-field-full">
            <label htmlFor="res-name">
              Resource Name <span className="req-star">*</span>
            </label>
            <input
              id="res-name"
              type="text"
              required
              minLength={2}
              maxLength={120}
              placeholder="e.g. City Hospital Ambulance Unit A"
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              disabled={submitting}
            />
            {fieldErrors.name && <span className="field-error">{fieldErrors.name}</span>}
          </div>

          <div className="form-field">
            <label htmlFor="res-location">
              Depot / Location <span className="req-star">*</span>
            </label>
            <input
              id="res-location"
              type="text"
              required
              minLength={2}
              maxLength={200}
              placeholder="e.g. Central Depot, Ward 4"
              value={form.location}
              onChange={(e) => setForm((f) => ({ ...f, location: e.target.value }))}
              disabled={submitting}
            />
            {fieldErrors.location && (
              <span className="field-error">{fieldErrors.location}</span>
            )}
          </div>

          <div className="form-field">
            <label htmlFor="res-latitude">Latitude (optional)</label>
            <input
              id="res-latitude"
              type="number"
              min="-90"
              max="90"
              step="any"
              placeholder="e.g. 28.6139"
              value={form.latitude}
              onChange={(e) => setForm((f) => ({ ...f, latitude: e.target.value }))}
              disabled={submitting}
            />
            {fieldErrors.latitude && <span className="field-error">{fieldErrors.latitude}</span>}
          </div>

          <div className="form-field">
            <label htmlFor="res-longitude">Longitude (optional)</label>
            <input
              id="res-longitude"
              type="number"
              min="-180"
              max="180"
              step="any"
              placeholder="e.g. 77.2090"
              value={form.longitude}
              onChange={(e) => setForm((f) => ({ ...f, longitude: e.target.value }))}
              disabled={submitting}
            />
            {fieldErrors.longitude && <span className="field-error">{fieldErrors.longitude}</span>}
            <span className="field-hint">Enter both coordinates to include this resource in the map and nearby matching.</span>
          </div>

          {editingResourceId !== null && (
            <div className="form-field form-field-full">
              <label htmlFor="res-audit-note">Change note (optional)</label>
              <input
                id="res-audit-note"
                type="text"
                maxLength={500}
                placeholder="Reason for this inventory change…"
                value={form.note}
                onChange={(e) => setForm((current) => ({ ...current, note: e.target.value }))}
                disabled={submitting}
              />
            </div>
          )}

          <div className="form-field">
            <label htmlFor="res-status">
              Availability Status <span className="req-star">*</span>
            </label>
            <select
              id="res-status"
              value={form.availability_status}
              onChange={(e) =>
                setForm((f) => ({ ...f, availability_status: e.target.value }))
              }
              disabled={submitting}
            >
              {AVAILABILITY_STATUSES.map((st) => (
                <option key={st} value={st}>
                  {labelize(st)}
                </option>
              ))}
            </select>
            {fieldErrors.availability_status && (
              <span className="field-error">{fieldErrors.availability_status}</span>
            )}
          </div>
        </form>
      </Modal>
    </div>
  );
}

