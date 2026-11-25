import { useEffect, useState } from "react";

/**
 * Tiny hash-based router (no extra dependency).
 *   #/                         -> dashboard
 *   #/incidents                -> incidents
 *   #/incidents/12?rec=5       -> incident (id 12, query.rec = "5")
 *   #/resources | #/recommendations | #/dispatch | #/history
 */
export function parseHash(hash) {
  const raw = (hash || "").replace(/^#/, "") || "/";
  const [pathPart, queryPart = ""] = raw.split("?");
  const segments = pathPart.split("/").filter(Boolean);
  const query = Object.fromEntries(new URLSearchParams(queryPart));

  if (segments.length === 0) return { name: "dashboard", query };

  const [first, second] = segments;
  if (first === "incidents" && second) {
    const id = Number(second);
    return Number.isInteger(id) && id > 0 ? { name: "incident", id, query } : { name: "notfound", query };
  }
  if (["incidents", "resources", "recommendations", "dispatch", "history"].includes(first) && !second) {
    return { name: first, query };
  }
  return { name: "notfound", query };
}

export function navigate(path) {
  window.location.hash = path;
}

export function useHashRoute() {
  const [route, setRoute] = useState(() => parseHash(window.location.hash));

  useEffect(() => {
    const onChange = () => {
      setRoute(parseHash(window.location.hash));
      window.scrollTo({ top: 0 });
    };
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);

  return route;
}

