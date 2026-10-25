import { useSyncExternalStore } from "react";
import { ApiError } from "./client";

// The backend serves only users registered through the bot (/start) and
// answers everyone else with 403 "User not registered".
const NOT_REGISTERED_DETAIL = "User not registered";

export function isNotRegisteredError(error: unknown): boolean {
  return (
    error instanceof ApiError &&
    error.status === 403 &&
    error.message === NOT_REGISTERED_DETAIL
  );
}

// Set once any request is rejected as not registered; the app then shows a
// prompt to start the bot instead of per-page error states.
let notRegistered = false;
const listeners = new Set<() => void>();

export function markNotRegistered(): void {
  if (notRegistered) return;
  notRegistered = true;
  listeners.forEach((listener) => listener());
}

export function resetNotRegistered(): void {
  notRegistered = false;
  listeners.forEach((listener) => listener());
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useNotRegistered(): boolean {
  return useSyncExternalStore(subscribe, () => notRegistered);
}

// Auth failures won't succeed on retry.
export function shouldRetry(failureCount: number, error: unknown): boolean {
  if (
    error instanceof ApiError &&
    (error.status === 401 || error.status === 403)
  )
    return false;
  return failureCount < 1;
}
