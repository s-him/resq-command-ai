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
export default function IncidentMapPanel({ incidents = [] }) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const layerRef = useRef(null);

  const mapped = incidents.filter(hasValidCoordinates);
  const unmappedCount = incidents.length - mapped.length;

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

    if (mapped.length === 0) {
      map.setView(DEFAULT_CENTER, DEFAULT_ZOOM);
      return;
    }

    const bounds = [];

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
  }, [incidents, mapped.length]);

  return (
    <section className="surface-card">
      <div className="panel-header">
        <div>
          <h2 className="section-title">
            Geospatial Incident Overview (Reported / Sample Coordinates)
          </h2>
          <p className="section-subtitle">
            Plots only incidents supplied with valid latitude and longitude. No live tracking,
            geocoding, or external feeds are used.
          </p>
        </div>

        <div className="map-legend" aria-label="Severity marker legend">
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
                {incidents.length === 0
                  ? "Report an incident with optional latitude and longitude to display its marker here."
                  : `All ${incidents.length} reported incident(s) omit optional coordinates and remain listed in the priority queue above.`}
              </p>
            </div>
          </div>
        )}
      </div>

      <div className="map-footer">
        <span className="tabular">
          <Icon name="compass" size={14} />{" "}
          <strong>{mapped.length}</strong> mapped incident(s) with reported/sample coordinates
          {unmappedCount > 0 &&
            ` · ${unmappedCount} incident(s) without coordinates shown in the queue`}
        </span>
        <span className="text-muted">
          Click a marker to inspect details · Double-click a marker to open its investigation page
        </span>
      </div>
    </section>
  );
}

