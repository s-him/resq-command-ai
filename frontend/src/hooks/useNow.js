import { useEffect, useState } from "react";

/** Re-renders the caller every `intervalMs` so relative times ("2 min ago") stay fresh. */
export function useNow(intervalMs = 30000) {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), intervalMs);
    return () => clearInterval(timer);
  }, [intervalMs]);
  return now;
}

