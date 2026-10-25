// After a deploy, a page loaded from the previous build still asks for its
// old lazy-loaded chunks, which no longer exist; Vite reports that as a
// `vite:preloadError` event. Reloading picks up the new build. A reload within
// RELOAD_GUARD_MS of the last one is skipped, so a chunk that keeps failing
// falls through to the error boundary instead of reloading in a loop.

const LAST_RELOAD_KEY = "stale-chunk-reload-at";
export const RELOAD_GUARD_MS = 10_000;

interface Deps {
  target: Pick<EventTarget, "addEventListener">;
  storage: Pick<Storage, "getItem" | "setItem"> | undefined;
  reload: () => void;
  now: () => number;
}

function defaultStorage(): Storage | undefined {
  try {
    return window.sessionStorage;
  } catch {
    return undefined;
  }
}

export function installStaleChunkReload(
  deps: Deps = {
    target: window,
    storage: defaultStorage(),
    reload: () => window.location.reload(),
    now: () => Date.now(),
  },
): void {
  deps.target.addEventListener("vite:preloadError", (event) => {
    let lastReload: number | null = null;
    try {
      const stored = deps.storage?.getItem(LAST_RELOAD_KEY);
      if (stored) lastReload = Number(stored);
    } catch {
      // Storage unavailable: treat as never reloaded
    }
    if (lastReload !== null && deps.now() - lastReload < RELOAD_GUARD_MS)
      return;

    try {
      deps.storage?.setItem(LAST_RELOAD_KEY, String(deps.now()));
    } catch {
      // Without storage the guard can't persist; reload anyway
    }
    event.preventDefault();
    deps.reload();
  });
}
