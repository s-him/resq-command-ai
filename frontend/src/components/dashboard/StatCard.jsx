import React from "react";
import Icon from "../common/Icon";

/**
 * Restrained enterprise metric card: neutral white surface, subtle border,
 * quiet uppercase label, balanced tabular numeral, and clear context line.
 */
export default function StatCard({
  label,
  value,
  meta,
  icon,
  indicator = "neutral",
  onClick,
}) {
  const Tag = onClick ? "button" : "div";
  return (
    <Tag
      type={onClick ? "button" : undefined}
      className={`surface-card stat-card ${onClick ? "stat-card-clickable" : ""}`.trim()}
      onClick={onClick}
    >
      <div className="stat-card-top">
        <span className="stat-label">{label}</span>
        {icon && (
          <span className={`stat-icon stat-icon-${indicator}`} aria-hidden="true">
            <Icon name={icon} size={15} />
          </span>
        )}
      </div>
      <div className="stat-value tabular">{value}</div>
      {meta && <div className="stat-meta">{meta}</div>}
    </Tag>
  );
}
