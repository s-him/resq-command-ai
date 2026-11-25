import React from "react";
import { describeError } from "../../services/apiClient";
import Icon from "./Icon";

export default function ErrorState({
  title = "Unable to load backend data",
  error,
  onRetry,
}) {
  const message = describeError(error);
  return (
    <div className="error-panel" role="alert">
      <div className="error-panel-main">
        <Icon name="alertCircle" size={20} className="error-panel-icon" />
        <div>
          <h3 className="error-panel-title">{title}</h3>
          {message && <p className="error-panel-msg">{message}</p>}
        </div>
      </div>
      {onRetry && (
        <button type="button" className="btn btn-secondary btn-sm" onClick={onRetry}>
          <Icon name="refresh" size={14} />
          <span>Retry</span>
        </button>
      )}
    </div>
  );
}

