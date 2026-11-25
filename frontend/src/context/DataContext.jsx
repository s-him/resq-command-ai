import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { getHealth } from "../services/healthService";
import { getIncidentHistory, getPriorityQueue, listIncidents } from "../services/incidentService";
import { listResources } from "../services/resourceService";

/**
 * Shared backend data for the whole app.
 *
 * The backend has no global "list recommendations" or "list all history"
 * endpoint, so recommendations and action history are collected from
 * GET /api/incidents/{id}/history for each incident. Nothing is invented.
 */
const DataContext = createContext(null);

const initialSlice = (data) => ({ data, loading: true, error: null });

export function DataProvider({ children }) {
  const [health, setHealth] = useState({ state: "checking", info: null, checkedAt: null, error: null });
  const [priority, setPriority] = useState(initialSlice(null));
  const [incidents, setIncidents] = useState(initialSlice([]));
  const [resources, setResources] = useState(initialSlice([]));
  const [histories, setHistories] = useState({ data: {}, loading: true, error: null, failedIds: [] });
  const [lastUpdated, setLastUpdated] = useState(null);
  const [refreshing, setRefreshing] = useState(false);
  const inFlight = useRef(false);

  const checkHealth = useCallback(async ({ silent = false } = {}) => {
    if (!silent) setHealth((current) => ({ ...current, state: "checking" }));
    try {
      const info = await getHealth();
      const ok = info.status === "ok";
      setHealth({
        state: ok ? "connected" : "unavailable",
        info,
        checkedAt: new Date(),
        error: ok ? null : "The backend responded but reported its database as unavailable.",
      });
    } catch (error) {
      setHealth({ state: "unavailable", info: null, checkedAt: new Date(), error: error.message });
    }
  }, []);

  const loadHistories = useCallback(async (incidentList) => {
    setHistories((current) => ({ ...current, loading: true, error: null }));
    const results = await Promise.allSettled(incidentList.map((inc) => getIncidentHistory(inc.id)));
    const data = {};
    const failedIds = [];
    results.forEach((result, index) => {
      const id = incidentList[index].id;
      if (result.status === "fulfilled") data[id] = result.value;
      else failedIds.push(id);
    });
    setHistories({
      data,
      loading: false,
      failedIds,
      error: failedIds.length
        ? new Error(`History could not be loaded for ${failedIds.length} incident(s).`)
        : null,
    });
  }, []);

  const refreshAll = useCallback(async () => {
    if (inFlight.current) return;
    inFlight.current = true;
    setRefreshing(true);
    try {
      const healthCheck = checkHealth();
      setPriority((s) => ({ ...s, loading: true }));
      setIncidents((s) => ({ ...s, loading: true }));
      setResources((s) => ({ ...s, loading: true }));

      const [p, i, r] = await Promise.allSettled([getPriorityQueue(), listIncidents(), listResources()]);

      if (p.status === "fulfilled") setPriority({ data: p.value, loading: false, error: null });
      else setPriority((s) => ({ ...s, loading: false, error: p.reason }));

      if (i.status === "fulfilled") setIncidents({ data: i.value, loading: false, error: null });
      else setIncidents((s) => ({ ...s, loading: false, error: i.reason }));

      if (r.status === "fulfilled") setResources({ data: r.value, loading: false, error: null });
      else setResources((s) => ({ ...s, loading: false, error: r.reason }));

      if (i.status === "fulfilled") await loadHistories(i.value);
      else setHistories((s) => ({ ...s, loading: false, error: i.reason }));

      await healthCheck;
      if ([p, i, r].every((result) => result.status === "fulfilled")) setLastUpdated(new Date());
    } finally {
      inFlight.current = false;
      setRefreshing(false);
    }
  }, [checkHealth, loadHistories]);

  /** Re-fetch one incident's history (after generating or deciding a recommendation). */
  const refreshIncidentHistory = useCallback(async (incidentId) => {
    const history = await getIncidentHistory(incidentId);
    setHistories((s) => ({ ...s, data: { ...s.data, [incidentId]: history } }));
    return history;
  }, []);

  useEffect(() => {
    refreshAll();
    const timer = setInterval(() => checkHealth({ silent: true }), 30000);
    return () => clearInterval(timer);
  }, [refreshAll, checkHealth]);

  const derived = useMemo(() => {
    const allHistories = Object.values(histories.data);
    const recommendations = allHistories.flatMap((h) => h.recommendations).sort((a, b) => b.id - a.id);
    const actions = allHistories.flatMap((h) => h.action_history).sort((a, b) => b.id - a.id);
    const incidentIndex = Object.fromEntries(incidents.data.map((inc) => [inc.id, inc]));
    const priorityIndex = Object.fromEntries((priority.data?.incidents || []).map((inc) => [inc.id, inc]));
    return { recommendations, actions, incidentIndex, priorityIndex };
  }, [histories.data, incidents.data, priority.data]);

  const value = {
    health,
    priority,
    incidents,
    resources,
    histories,
    lastUpdated,
    refreshing,
    refreshAll,
    checkHealth,
    refreshIncidentHistory,
    ...derived,
  };

  return <DataContext.Provider value={value}>{children}</DataContext.Provider>;
}

export function useData() {
  const context = useContext(DataContext);
  if (!context) throw new Error("useData must be used inside <DataProvider>.");
  return context;
}

