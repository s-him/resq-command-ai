/**
 * Central HTTP client. Every backend request in the app goes through `request()`.
 *
 * Errors are normalised into ApiError with a `kind`:
 *   network | validation | not_found | conflict | server | http | format
 */

import { API_BASE_URL } from "../config.js";

export class ApiError extends Error {
  constructor(message, { status = null, kind = "http", fieldErrors = {}, details = [] } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.kind = kind;
    this.fieldErrors = fieldErrors; // { field_name: "first message" }
    this.details = details; // raw [{ field, message }] from FastAPI 422 responses
  }
}

function defaultMessage(status) {
  if (status === 404) return "The requested record was not found.";
  if (status === 409) return "This action conflicts with the current state of the record.";
  if (status >= 500) return "The backend encountered an internal error. Please try again.";
  return `The request failed (HTTP ${status}).`;
}

function kindForStatus(status) {
  if (status === 404) return "not_found";
  if (status === 409) return "conflict";
  if (status >= 500) return "server";
  return "http";
}

export async function request(path, { method = "GET", body, signal } = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method,
      signal,
      // Only send a JSON content type when there is a body (keeps GETs simple for CORS).
      headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch (error) {
    if (error?.name === "AbortError") throw error;
    throw new ApiError(
      `Cannot reach the backend at ${API_BASE_URL}. Check that the FastAPI server is running.`,
      { kind: "network" }
    );
  }

  const text = await response.text();
  let data = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      throw new ApiError("The backend returned a response that is not valid JSON.", {
        status: response.status,
        kind: "format",
      });
    }
  }

  if (!response.ok) {
    if (response.status === 422 && data && Array.isArray(data.errors)) {
      const fieldErrors = {};
      for (const error of data.errors) {
        // "help_needed.1" -> "help_needed" so the message lands on the right form field.
        const key = String(error.field || "body").split(".")[0];
        if (!fieldErrors[key]) fieldErrors[key] = error.message;
      }
      throw new ApiError(data.detail || "Validation failed", {
        status: 422,
        kind: "validation",
        fieldErrors,
        details: data.errors,
      });
    }
    const detail = data && typeof data.detail === "string" ? data.detail : null;
    throw new ApiError(detail || defaultMessage(response.status), {
      status: response.status,
      kind: kindForStatus(response.status),
    });
  }

  return data;
}

export function expectArray(data, label) {
  if (!Array.isArray(data)) {
    throw new ApiError(`Unexpected response format from ${label} (expected a list).`, { kind: "format" });
  }
  return data;
}

export function expectObject(data, label, requiredKeys = []) {
  if (!data || typeof data !== "object" || Array.isArray(data)) {
    throw new ApiError(`Unexpected response format from ${label}.`, { kind: "format" });
  }
  const missing = requiredKeys.filter((key) => !(key in data));
  if (missing.length) {
    throw new ApiError(`Unexpected response from ${label}: missing ${missing.join(", ")}.`, {
      kind: "format",
    });
  }
  return data;
}

/** Human-readable text for any error thrown by the services. */
export function describeError(error) {
  if (!error) return "";
  if (typeof error === "string") return error;
  if (error instanceof ApiError && error.kind === "validation" && error.details.length) {
    return `${error.message}: ${error.details.map((d) => `${d.field} – ${d.message}`).join("; ")}`;
  }
  return error.message || "Something went wrong.";
}

