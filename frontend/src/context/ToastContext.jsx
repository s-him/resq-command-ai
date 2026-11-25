import { createContext, useCallback, useContext, useState } from "react";
import Icon from "../components/common/Icon";

/**
 * Frontend operation feedback only (form saved, request failed, ...).
 * These are NOT emergency alerts - the backend has no alerts endpoint.
 */
const ToastContext = createContext(null);

const TOAST_ICONS = { success: "checkCircle", error: "alertCircle", warning: "alert", info: "info" };

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);

  const dismiss = useCallback((id) => {
    setToasts((list) => list.map((t) => (t.id === id ? { ...t, leaving: true } : t)));
    setTimeout(() => setToasts((list) => list.filter((t) => t.id !== id)), 220);
  }, []);

  const push = useCallback(
    ({ type = "info", title, message, duration = 5000 }) => {
      const id = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
      setToasts((list) => [...list.slice(-3), { id, type, title, message }]);
      if (duration) setTimeout(() => dismiss(id), duration);
    },
    [dismiss]
  );

  return (
    <ToastContext.Provider value={push}>
      {children}
      <div className="toast-region" aria-live="polite" aria-label="Notifications">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={`toast toast-${toast.type}${toast.leaving ? " is-leaving" : ""}`}
            role={toast.type === "error" ? "alert" : "status"}
          >
            <Icon name={TOAST_ICONS[toast.type]} size={18} className="toast-icon" />
            <div className="toast-body">
              {toast.title && <p className="toast-title">{toast.title}</p>}
              {toast.message && <p className="toast-message">{toast.message}</p>}
            </div>
            <button
              type="button"
              className="icon-btn icon-btn-sm"
              onClick={() => dismiss(toast.id)}
              aria-label="Dismiss notification"
            >
              <Icon name="x" size={14} />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) throw new Error("useToast must be used inside <ToastProvider>.");
  return context;
}

