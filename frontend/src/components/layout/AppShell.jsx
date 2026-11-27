import React, { useLayoutEffect, useState } from "react";

import Sidebar from "./Sidebar";
import Topbar from "./Topbar";

const THEME_STORAGE_KEY = "resq-command-theme";

function getInitialTheme() {
  try {
    return window.localStorage.getItem(THEME_STORAGE_KEY) === "dark" ? "dark" : "light";
  } catch {
    return "light";
  }
}

export default function AppShell({ route, onOpenCreateIncident, children }) {
  const [theme, setTheme] = useState(getInitialTheme);
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  useLayoutEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme;

    const themeColor = document.querySelector('meta[name="theme-color"]');
    if (themeColor) {
      themeColor.setAttribute("content", theme === "dark" ? "#0D1714" : "#F8FBFA");
    }

    try {
      window.localStorage.setItem(THEME_STORAGE_KEY, theme);
    } catch {
      // The theme still works for this session when storage is unavailable.
    }
  }, [theme]);

  function toggleTheme() {
    setTheme((current) => (current === "light" ? "dark" : "light"));
  }

  return (
    <div className={`app-shell ${collapsed ? "sidebar-collapsed" : ""}`} data-theme={theme}>
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
          theme={theme}
          onToggleTheme={toggleTheme}
          onOpenMobileNav={() => setMobileOpen(true)}
          onOpenCreateIncident={onOpenCreateIncident}
        />
       
        <main className="app-content" id="main-content">
          {children}
        </main>
      </div>
    </div>
  );
}

