import React from "react";
import { API_BASE_URL } from "../../config";
import { useData } from "../../context/DataContext";
import { navigate } from "../../hooks/useHashRoute";
import Icon from "../common/Icon";

const NAV_GROUPS = [
  {
    heading: "OVERVIEW",
    items: [{ id: "dashboard", label: "Dashboard", path: "#/", icon: "grid" }],
  },
  {
    heading: "OPERATIONS",
    items: [
      { id: "incidents", label: "Incidents", path: "#/incidents", icon: "alert", countKey: "incidents" },
      { id: "resources", label: "Resources", path: "#/resources", icon: "package", countKey: "resources" },
      {
        id: "recommendations",
        label: "Recommendations",
        path: "#/recommendations",
        icon: "cpu",
        countKey: "pendingRecs",
      },
    ],
  },
  {
    heading: "MONITORING",
    items: [
      { id: "history", label: "Activity History", path: "#/history", icon: "history", countKey: "actions" },
    ],
  },
];

export default function Sidebar({
  route,
  collapsed,
  mobileOpen,
  onToggleCollapse,
  onCloseMobile,
}) {
  const { health, incidents, resources, recommendations, actions } = useData();

  const counts = {
    incidents: incidents.data.length,
    resources: resources.data.length,
    pendingRecs: recommendations.filter((r) => r.status === "pending").length,
    actions: actions.length,
  };

  const activeNavId = route.name === "incident" ? "incidents" : route.name;
  const appVersion =
    health.info?.version || (typeof __APP_VERSION__ !== "undefined" ? __APP_VERSION__ : "0.1.0");

  function handleNav(path) {
    navigate(path);
    onCloseMobile?.();
  }

  return (
    <>
      {mobileOpen && (
        <div
          className="sidebar-overlay"
          onClick={onCloseMobile}
          aria-hidden="true"
        />
      )}
      <aside
        className={`sidebar ${collapsed ? "is-collapsed" : ""} ${
          mobileOpen ? "is-mobile-open" : ""
        }`.trim()}
        aria-label="Primary navigation"
      >
        <div className="sidebar-brand">
          <div className="brand-mark" aria-hidden="true">
            <Icon name="shield" size={20} />
          </div>
          {!collapsed && (
            <div className="brand-copy">
              <div className="brand-title">RESQ COMMAND</div>
              <div className="brand-subtitle">MULTI-AGENT RESPONSE ENGINE</div>
            </div>
          )}
          <button
            type="button"
            className="sidebar-collapse-btn"
            onClick={onToggleCollapse}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            <Icon name={collapsed ? "chevronRight" : "chevronLeft"} size={16} />
          </button>
        </div>

        <nav className="sidebar-nav">
          {NAV_GROUPS.map((group) => (
            <div key={group.heading} className="nav-group">
              {!collapsed && <div className="nav-group-label">{group.heading}</div>}
              <ul className="nav-list">
                {group.items.map((item) => {
                  const isActive = activeNavId === item.id;
                  const count = item.countKey ? counts[item.countKey] : null;
                  return (
                    <li key={item.id}>
                      <button
                        type="button"
                        className={`nav-item ${isActive ? "is-active" : ""}`}
                        onClick={() => handleNav(item.path)}
                        aria-current={isActive ? "page" : undefined}
                        title={collapsed ? item.label : undefined}
                      >
                        <Icon name={item.icon} size={18} className="nav-item-icon" />
                        {!collapsed && <span className="nav-item-label">{item.label}</span>}
                        {!collapsed && typeof count === "number" && count > 0 && (
                          <span
                            className={`nav-count tabular ${
                              item.countKey === "pendingRecs" ? "nav-count-accent" : ""
                            }`}
                          >
                            {count}
                          </span>
                        )}
                      </button>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="sidebar-proto-pill">
            <span className="proto-dot" aria-hidden="true" />
            {!collapsed && <span>Academic Prototype · v{appVersion}</span>}
          </div>
          {!collapsed && (
            <div className="sidebar-endpoint" title={API_BASE_URL}>
              <Icon name="database" size={13} />
              <span className="tabular">{API_BASE_URL}</span>
              <span className={`conn-dot conn-${health.state}`} />
            </div>
          )}
        </div>
      </aside>
    </>
  );
}

