import React from "react";
import { incidentCode, recommendationCode } from "../../utils/format";
import Modal from "./Modal";

/**
 * Confirmation dialog before recording an operator decision.
 * Clean, understated enterprise modal explaining the prototype boundary.
 */
export default function ConfirmDialog({
  open,
  decision,
  recommendation,
  note,
  submitting,
  errorMessage = "",
  onCancel,
  onConfirm,
}) {
  if (!open || !recommendation) return null;

  const isApprove = decision === "approved";

  return (
    <Modal
      open={open}
      onClose={submitting ? undefined : onCancel}
      size="sm"
      title={
        isApprove
          ? `Approve Recommendation ${recommendationCode(recommendation.id)}`
          : `Reject Recommendation ${recommendationCode(recommendation.id)}`
      }
      subtitle={`Incident ${incidentCode(recommendation.incident_id)} · Operator Review Confirmation`}
      footer={
        <>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={onCancel}
            disabled={submitting}
          >
            Cancel
          </button>
          <button
            type="button"
            className={`btn ${isApprove ? "btn-teal" : "btn-danger"}`}
            onClick={onConfirm}
            disabled={submitting}
          >
            {submitting
              ? "Recording decision..."
              : isApprove
              ? "Confirm Approval"
              : "Confirm Rejection"}
          </button>
        </>
      }
    >
      <div className="confirm-content">
        <p className="confirm-lead">
          You are recording an operator decision of <strong>{decision}</strong> for{" "}
          <strong>{recommendationCode(recommendation.id)}</strong>.
        </p>

        <div className="confirm-summary">
          <div className="confirm-row">
            <span className="confirm-label">Related Incident</span>
            <span className="confirm-value tabular">
              {incidentCode(recommendation.incident_id)}
            </span>
          </div>
          <div className="confirm-row">
            <span className="confirm-label">Matched Resource Items</span>
            <span className="confirm-value tabular">
              {recommendation.items?.length || 0} item(s)
            </span>
          </div>
          <div className="confirm-row">
            <span className="confirm-label">Decision</span>
            <span className="confirm-value" style={{ textTransform: "capitalize" }}>
              {decision}
            </span>
          </div>
          <div className="confirm-row">
            <span className="confirm-label">Operator Note</span>
            <span className="confirm-value">
              {note && note.trim() ? note.trim() : "No note provided"}
            </span>
          </div>
        </div>

        {errorMessage && (
          <p className="field-error" role="alert">{errorMessage}</p>
        )}

        <div className="confirm-boundary-note">
          <strong>Prototype boundary:</strong> Confirming records this decision and appends an
          action-history entry. Approval rechecks and earmarks the recommended capacity without
          changing physical inventory. Approving a response plan converts that hold into a virtual
          reservation; rejected or completed plans release it. No real responder is dispatched.
        </div>
      </div>
    </Modal>
  );
}
