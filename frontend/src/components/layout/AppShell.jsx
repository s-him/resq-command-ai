import React, { useState } from "react";
import SafetyBanner from "./SafetyBanner";
import Sidebar from "./Sidebar";
import Topbar from "./Topbar";

export default function AppShell({ route, onOpenCreateIncident, children }) {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className={`app-shell ${collapsed ? "sidebar-collapsed" : ""}`}>
      <Sidebar
        route={route}
        collapsed={collapsed}
        mobileOpen={mobileOpen}
        onToggleCollapse={() => setCollapsed((c) => !c)}
        onCloseMobile={() => setMobileOpen(false)}
      />

      <div className="app-main">
        <Topbar
          route={route}
          onOpenMobileNav={() => setMobileOpen(true)}
          onOpenCreateIncident={onOpenCreateIncident}
        />
        <SafetyBanner />
        <main className="app-content" id="main-content">
          {children}
        </main>
      </div>
    </div>
  );
}

