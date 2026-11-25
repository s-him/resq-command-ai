/**
 * Backend address configuration (single place to change it).
 *
 * Defaults to the local FastAPI server on port 8000.
 * You can override this by creating a `frontend/.env` file with:
 *   VITE_API_BASE_URL=http://127.0.0.1:8000
 */
export const API_BASE_URL = (
  import.meta.env?.VITE_API_BASE_URL || "http://127.0.0.1:8000"
).replace(/\/$/, "");

