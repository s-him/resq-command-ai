import React from "react";
import Icon from "../common/Icon";

const STAGES = [
  {
    key: "report",
    step: "01",
    title: "Incident Report",
    desc: "Validated in SQLite",
  },
  {
    key: "severity",
    step: "02",
    title: "Severity Score",
    desc: "0–100 rule evaluation",
  },
  {
    key: "priority",
    step: "03",
    title: "Priority Queue",
    desc: "Multi-factor tie-breaking",
  },
  {
    key: "matching",
    step: "04",
    title: "Resource Match",
    desc: "Inventory comparison",
  },
  {
    key: "review",
    step: "05",
    title: "Operator Review",
    desc: "Human oversight gate",
  },
  {
    key: "decision",
    step: "06",
    title: "Audit Decision",
    desc: "Logged in action history",
  },
];

/**
 * Compact horizontal workflow strip. Stages only show as active when real
 * database records exist for that stage.
 */
export default function WorkflowOverview({
  incidentCount = 0,
  prioritizedCount = 0,
  recommendationCount = 0,
  decisionCount = 0,
}) {
  const activeMap = {
    report: incidentCount > 0,
    severity: incidentCount > 0,
    priority: prioritizedCount > 0,
    matching: recommendationCount > 0,
    review: recommendationCount > 0,
    decision: decisionCount > 0,
  };

  return (
    <section className="surface-card workflow-card" aria-label="Operational workflow pipeline">
      <div className="workflow-header">
        <div>
          <h2 className="section-title">Decision-Support Pipeline</h2>
          <p className="section-subtitle">
            Each stage reflects records currently stored in the backend database.
          </p>
        </div>
        <span className="meta-tag">Human-in-the-Loop</span>
      </div>

      <ol className="workflow-strip">
        {STAGES.map((stage) => {
          const isVerified = Boolean(activeMap[stage.key]);
          return (
            <li
              key={stage.key}
              className={`workflow-node ${isVerified ? "is-verified" : ""}`}
            >
              <div className="workflow-node-head">
                <span className="workflow-step-num tabular">{stage.step}</span>
                {isVerified ? (
                  <span className="workflow-status-active">
                    <Icon name="check" size={12} />
                    <span>Recorded</span>
                  </span>
                ) : (
                  <span className="workflow-status-idle">Pending</span>
                )}
              </div>
              <div className="workflow-node-title">{stage.title}</div>
              <div className="workflow-node-desc">{stage.desc}</div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
