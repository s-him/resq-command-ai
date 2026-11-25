import React, { useState } from "react";
import EmptyState from "./components/common/EmptyState";
import IncidentFormModal from "./components/incidents/IncidentFormModal";
import AppShell from "./components/layout/AppShell";
import { DataProvider } from "./context/DataContext";
import { ToastProvider } from "./context/ToastContext";
import { navigate, useHashRoute } from "./hooks/useHashRoute";
import ActivityHistory from "./pages/ActivityHistory";
import Dashboard from "./pages/Dashboard";
import IncidentDetails from "./pages/IncidentDetails";
import Incidents from "./pages/Incidents";
import Recommendations from "./pages/Recommendations";
import Resources from "./pages/Resources";
import ResponsePlans from "./pages/ResponsePlans";

function RoutedWorkspace({ route, onOpenCreateIncident }) {
  switch (route.name) {
    case "dashboard":
      return <Dashboard onOpenCreateIncident={onOpenCreateIncident} />;
    case "incidents":
      return <Incidents onOpenCreateIncident={onOpenCreateIncident} />;
    case "incident":
      return <IncidentDetails incidentId={route.id} />;
    case "resources":
      return <Resources />;
    case "recommendations":
      return <Recommendations />;
    case "dispatch":
      return <ResponsePlans />;
    case "history":
      return <ActivityHistory />;
    default:
      return (
        <div className="surface-card">
          <EmptyState
            icon="compass"
            title="Page not found"
            description="The requested view does not exist in this prototype."
            actionLabel="Return to Operational Overview"
            onAction={() => navigate("#/")}
          />
        </div>
      );
  }
}

export default function App() {
  const route = useHashRoute();
  const [createModalState, setCreateModalState] = useState({
    open: false,
    preset: null,
  });

  function handleOpenCreateIncident(preset = null) {
    setCreateModalState({ open: true, preset: typeof preset === "string" ? preset : null });
  }

  return (
    <ToastProvider>
      <DataProvider>
        <AppShell route={route} onOpenCreateIncident={handleOpenCreateIncident}>
          <RoutedWorkspace
            route={route}
            onOpenCreateIncident={handleOpenCreateIncident}
          />
        </AppShell>

        <IncidentFormModal
          open={createModalState.open}
          initialPreset={createModalState.preset}
          onClose={() => setCreateModalState({ open: false, preset: null })}
        />
      </DataProvider>
    </ToastProvider>
  );
}
