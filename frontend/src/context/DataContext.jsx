import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { API_BASE_URL } from "../config";
import { getHealth } from "../services/healthService";
import { getAreaPriority, getIncidentHistory, getPriorityQueue, listIncidents } from "../services/incidentService";
import { listResources } from "../services/resourceService";
import { listAlerts } from "../services/alertService";
import { listResponsePlans } from "../services/responsePlanService";

const DataContext = createContext(null);
const initialSlice = (data) => ({ data, loading: true, error: null });

/**
 * Shared data for the whole app. SSE carries invalidation notices only;
 * the REST API remains the source of truth for displayed values.
 */
export function DataProvider({ children }) {
  const [health, setHealth] = useState({ state: "checking", info: null, checkedAt: null, error: null });
  const [liveStatus, setLiveStatus] = useState("connecting");
  const [priority, setPriority] = useState(initialSlice(null));
  const [areaPriority, setAreaPriority] = useState(initialSlice(null));
  const [incidents, setIncidents] = useState(initialSlice([]));
  const [resources, setResources] = useState(initialSlice([]));
  const [alerts, setAlerts] = useState(initialSlice([]));
  const [responsePlans, setResponsePlans] = useState(initialSlice([]));
  const [histories, setHistories] = useState({ data: {}, loading: true, error: null, failedIds: [] });
  const [lastUpdated, setLastUpdated] = useState(null);
  const [refreshing, setRefreshing] = useState(false);
  const inFlight = useRef(false);
  const refreshQueued = useRef(false);
  const refreshAllRef = useRef(null);

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
    if (inFlight.current) {
      refreshQueued.current = true;
      return;
    }
    inFlight.current = true;
    setRefreshing(true);
    try {
      const healthCheck = checkHealth();
      setPriority((s) => ({ ...s, loading: true }));
      setAreaPriority((s) => ({ ...s, loading: true }));
      setIncidents((s) => ({ ...s, loading: true }));
      setResources((s) => ({ ...s, loading: true }));
      setAlerts((s) => ({ ...s, loading: true }));
      setResponsePlans((s) => ({ ...s, loading: true }));

      const [p, i, r, a, alertResult, planResult] = await Promise.allSettled([
        getPriorityQueue(),
        listIncidents(),
        listResources(),
        getAreaPriority(),
        listAlerts({ limit: 100 }),
        listResponsePlans(),
      ]);

      if (p.status === "fulfilled") setPriority({ data: p.value, loading: false, error: null });
      else setPriority((s) => ({ ...s, loading: false, error: p.reason }));

      if (i.status === "fulfilled") setIncidents({ data: i.value, loading: false, error: null });
      else setIncidents((s) => ({ ...s, loading: false, error: i.reason }));

      if (r.status === "fulfilled") setResources({ data: r.value, loading: false, error: null });
      else setResources((s) => ({ ...s, loading: false, error: r.reason }));

      if (a.status === "fulfilled") setAreaPriority({ data: a.value, loading: false, error: null });
      else setAreaPriority((s) => ({ ...s, loading: false, error: a.reason }));

      if (alertResult.status === "fulfilled") setAlerts({ data: alertResult.value.alerts, loading: false, error: null });
      else setAlerts((s) => ({ ...s, loading: false, error: alertResult.reason }));

      if (planResult.status === "fulfilled") setResponsePlans({ data: planResult.value.plans, loading: false, error: null });
      else setResponsePlans((s) => ({ ...s, loading: false, error: planResult.reason }));

      if (i.status === "fulfilled") await loadHistories(i.value);
      else setHistories((s) => ({ ...s, loading: false, error: i.reason }));

      await healthCheck;
      if ([p, i, r, a, alertResult, planResult].every((result) => result.status === "fulfilled")) {
        setLastUpdated(new Date());
      }
    } finally {
      inFlight.current = false;
      setRefreshing(false);
      if (refreshQueued.current) {
        refreshQueued.current = false;
        Promise.resolve().then(() => refreshAllRef.current?.());
      }
    }
  }, [checkHealth, loadHistories]);
  refreshAllRef.current = refreshAll;

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

  useEffect(() => {
    let fallbackTimer = null;
    let source = null;
    let disposed = false;

    const startFallback = () => {
      if (fallbackTimer || disposed) return;
      fallbackTimer = setInterval(() => refreshAll(), 10000);
    };
    const stopFallback = () => {
      if (!fallbackTimer) return;
      clearInterval(fallbackTimer);
      fallbackTimer = null;
    };

    if (typeof EventSource === "undefined") {
      setLiveStatus("polling");
      startFallback();
    } else {
      setLiveStatus("connecting");
      try {
        source = new EventSource(`${API_BASE_URL}/api/events/stream`);
        source.onopen = () => {
          if (disposed) return;
          setLiveStatus("live");
          stopFallback();
          refreshAll();
        };
        source.onmessage = (message) => {
          if (disposed) return;
          try {
            JSON.parse(message.data);
          } catch {
            return;
          }
          refreshAll();
        };
        source.onerror = () => {
          if (disposed) return;
          setLiveStatus("reconnecting");
          startFallback();
        };
      } catch {
        setLiveStatus("polling");
        startFallback();
      }
    }

    return () => {
      disposed = true;
      stopFallback();
      if (source) source.close();
    };
  }, [refreshAll]);

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
    liveStatus,
    priority,
    areaPriority,
    incidents,
    resources,
    alerts,
    responsePlans,
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
