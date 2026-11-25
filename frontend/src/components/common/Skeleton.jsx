import React from "react";

export function SkeletonBlock({ height = 16, width = "100%", className = "" }) {
  return (
    <div
      className={`skeleton-block ${className}`.trim()}
      style={{ height, width }}
      aria-hidden="true"
    />
  );
}

export function SkeletonStatCards({ count = 4 }) {
  return (
    <div className="stats-grid" aria-busy="true" aria-label="Loading statistics">
      {Array.from({ length: count }).map((_, idx) => (
        <div key={idx} className="surface-card stat-card">
          <SkeletonBlock height={14} width="45%" />
          <SkeletonBlock height={30} width="35%" />
          <SkeletonBlock height={12} width="75%" />
        </div>
      ))}
    </div>
  );
}

export function SkeletonTable({ rows = 4 }) {
  return (
    <div className="skeleton-table" aria-busy="true" aria-label="Loading records">
      {Array.from({ length: rows }).map((_, idx) => (
        <div key={idx} className="skeleton-row">
          <SkeletonBlock height={18} width="12%" />
          <SkeletonBlock height={18} width="22%" />
          <SkeletonBlock height={18} width="32%" />
          <SkeletonBlock height={18} width="18%" />
          <SkeletonBlock height={18} width="12%" />
        </div>
      ))}
    </div>
  );
}

