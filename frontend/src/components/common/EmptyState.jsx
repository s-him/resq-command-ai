import React from "react";
import Icon from "./Icon";

export default function EmptyState({
  icon = "layers",
  title = "No records found",
  description,
  actionLabel,
  onAction,
  secondaryActionLabel,
  onSecondaryAction,
}) {
  return (
    <div className="empty-panel">
      <div className="empty-icon-wrap">
        <Icon name={icon} size={22} />
      </div>
      <h3 className="empty-title">{title}</h3>
      {description && <p className="empty-desc">{description}</p>}
      {(actionLabel || secondaryActionLabel) && (
        <div className="empty-actions">
          {actionLabel && onAction && (
            <button type="button" className="btn btn-primary" onClick={onAction}>
              <Icon name="plus" size={16} />
              <span>{actionLabel}</span>
            </button>
          )}
          {secondaryActionLabel && onSecondaryAction && (
            <button type="button" className="btn btn-secondary" onClick={onSecondaryAction}>
              <span>{secondaryActionLabel}</span>
            </button>
          )}
        </div>
      )}
    </div>
  );
}

