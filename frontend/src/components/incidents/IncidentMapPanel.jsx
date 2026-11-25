import React, { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { navigate } from "../../hooks/useHashRoute";
import { SEVERITY_COLORS, SEVERITY_LEVELS } from "../../utils/constants";
import { incidentCode, labelize } from "../../utils/format";
import Icon from "../common/Icon";

const DEFAULT_CENTER = [20.5937, 78.9629];
const DEFAULT_ZOOM = 4;

export function hasValidCoordinates(incident) {
  return (
    typeof incident?.latitude === "number" &&
    typeof incident?.longitude === "number" &&
    Number.isFinite(incident.latitude) &&
    Number.isFinite(incident.longitude) &&
    incident.latitude >= -90 &&
    incident.latitude <= 90 &&
    incident.longitude >= -180 &&
    incident.longitude <= 180
  );
}

function escapeHtml(text) {
  return String(text ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/**
 * Leaflet geospatial overview of reported/sample incident coordinates.
 * Never invents or geocodes coordinates; incidents without coordinates remain visible
 * in all incident tables and lists.
 */
export default function IncidentMapPanel({ incidents = [], resources = [] }) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const layerRef = useRef(null);

  const mapped = incidents.filter(hasValidCoordinates);
  const mappedResources = resources.filter(hasValidCoordinates);
  const unmappedCount = incidents.length - mapped.length;
  const unmappedResourcesCount = resources.length - mappedResources.length;

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = L.map(containerRef.current, {
      center: DEFAULT_CENTER,
      zoom: DEFAULT_ZOOM,
    });

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      maxZoom: 18,
    }).addTo(map);

    layerRef.current = L.layerGroup().addTo(map);
    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
      layerRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    const layer = layerRef.current;
    if (!map || !layer) return;

    layer.clearLayers();

    if (mapped.length === 0 && mappedResources.length === 0) {
      map.setView(DEFAULT_CENTER, DEFAULT_ZOOM);
      return;
    }

    const bounds = [];

    mappedResources.forEach((resource) => {
      const status = resource.availability_status || "unknown";
      const color =
        status === "available" ? "#0F9D8A" :
        status === "limited" ? "#D97706" : "#64748B";
      const marker = L.circleMarker([resource.latitude, resource.longitude], {
        radius: 7,
        color: "#FFFFFF",
        weight: 2,
        fillColor: color,
        fillOpacity: 0.95,
      });

      const code = escapeHtml(`RES-${String(resource.id).padStart(4, "0")}`);
      const name = escapeHtml(resource.name);
      const type = escapeHtml(labelize(resource.resource_type));
      const location = escapeHtml(resource.location);
      const quantity = escapeHtml(resource.quantity_available);
      const availability = escapeHtml(labelize(status));

      marker.bindPopup(
        `<div class="map-popup">
          <div class="map-popup-head"><strong>${code}</strong> · Resource</div>
          <div><strong>Name:</strong> ${name}</div>
          <div><strong>Type:</strong> ${type}</div>
          <div><strong>Available quantity:</strong> ${quantity}</div>
          <div><strong>Status:</strong> ${availability}</div>
          <div><strong>Depot:</strong> ${location}</div>
          <div class="map-popup-coords">Registered coordinates: ${resource.latitude.toFixed(4)}, ${resource.longitude.toFixed(4)}</div>
          <div class="map-popup-coords">Straight-line distance is calculated only when matching to a located incident.</div>
        </div>`
      );

      marker.addTo(layer);
      bounds.push([resource.latitude, resource.longitude]);
    });

    mapped.forEach((incident) => {
      const level = incident.severity?.level || "Low";
      const color = SEVERITY_COLORS[level] || "#14B8A6";

      const marker = L.circleMarker([incident.latitude, incident.longitude], {
        radius: 9,
        color: "#101B2D",
        weight: 2,
        fillColor: color,
        fillOpacity: 0.92,
      });

      const code = escapeHtml(incidentCode(incident.id));
      const hazard = escapeHtml(labelize(incident.hazard_type));
      const loc = escapeHtml(incident.location);
      const sev = escapeHtml(level);

      marker.bindPopup(
        `<div class="map-popup">
          <div class="map-popup-head"><strong>${code}</strong> · ${hazard}</div>
          <div><strong>Severity:</strong> ${sev} (${incident.severity?.score ?? 0}/${
            incident.severity?.max_score ?? 100
          })</div>
          <div><strong>Location:</strong> ${loc}</div>
          <div class="map-popup-coords">Reported / sample coordinates: ${incident.latitude.toFixed(
            4
          )}, ${incident.longitude.toFixed(4)}</div>
          <div style="margin-top:6px"><a href="#/incidents/${incident.id}" class="map-popup-link">Open Incident Detail &rarr;</a></div>
        </div>`
      );

      marker.on("dblclick", () => navigate(`#/incidents/${incident.id}`));
      marker.addTo(layer);
      bounds.push([incident.latitude, incident.longitude]);
    });

    if (bounds.length === 1) {
      map.setView(bounds[0], 11);
    } else {
      map.fitBounds(bounds, { padding: [36, 36], maxZoom: 12 });
    }
  }, [incidents, mapped.length, mappedResources.length, resources]);

  return (
    <section className="surface-card">
      <div className="panel-header">
        <div>
          <h2 className="section-title">Incident &amp; Resource Geospatial Overview</h2>
          <p className="section-subtitle">
            Plots reported incident coordinates and registered resource depot coordinates. Missing locations are never guessed.
          </p>
        </div>

        <div className="map-legend" aria-label="Map marker legend">
          <span className="legend-pill">
            <span className="legend-dot" style={{ backgroundColor: "#0F9D8A" }} />
            <span>Resources</span>
          </span>
          {SEVERITY_LEVELS.map((level) => (
            <span key={level} className="legend-pill">
              <span
                className="legend-dot"
                style={{ backgroundColor: SEVERITY_COLORS[level] }}
              />
              <span>{level}</span>
            </span>
          ))}
        </div>
      </div>

      <div className="map-shell">
        <div ref={containerRef} className="leaflet-box" />
        {mapped.length === 0 && (
          <div className="map-empty-overlay">
            <Icon name="mapPin" size={20} />
            <div>
              <strong>No valid incident coordinates are currently available</strong>
              <p>
                {incidents.length === 0 && resources.length === 0
                  ? "Register a resource or report an incident with coordinates to display map markers here."
                  : "No records with coordinates are available yet. Records without coordinates remain visible in their tables and queues."}
              </p>
            </div>
          </div>
        )}
      </div>

      <div className="map-footer">
        <span className="tabular">
          <Icon name="compass" size={14} />{" "}
          <strong>{mapped.length}</strong> mapped incident(s)
          · <strong>{mappedResources.length}</strong> mapped resource(s)
          {(unmappedCount + unmappedResourcesCount) > 0 &&
            ` · ${unmappedCount} incident(s) and ${unmappedResourcesCount} resource(s) without coordinates`}
        </span>
        <span className="text-muted">
          Click a marker to inspect its record · Incident markers use severity colours; resource markers use green/amber/grey
        </span>
      </div>
    </section>
  );
}

