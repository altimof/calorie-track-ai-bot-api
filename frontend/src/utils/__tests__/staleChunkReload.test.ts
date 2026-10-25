import { describe, it, expect, vi } from "vitest";
import { installStaleChunkReload, RELOAD_GUARD_MS } from "../staleChunkReload";

function setup(start = 1_000_000) {
  const target = new EventTarget();
  const store = new Map<string, string>();
  const storage = {
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => void store.set(k, v),
  };
  const reload = vi.fn();
  let time = start;
  installStaleChunkReload({ target, storage, reload, now: () => time });

  const fire = () => {
    const event = new Event("vite:preloadError", { cancelable: true });
    target.dispatchEvent(event);
    return event;
  };
  return { fire, reload, advance: (ms: number) => (time += ms) };
}

describe("installStaleChunkReload", () => {
  it("reloads when a lazy chunk fails to load", () => {
    const { fire, reload } = setup();

    const event = fire();

    expect(reload).toHaveBeenCalledTimes(1);
    // preventDefault stops Vite from rethrowing while the page reloads
    expect(event.defaultPrevented).toBe(true);
  });

  it("does not reload again right after a reload", () => {
    const { fire, reload, advance } = setup();
    fire();
    advance(RELOAD_GUARD_MS - 1);

    const event = fire();

    expect(reload).toHaveBeenCalledTimes(1);
    // Vite rethrows, so the error boundary shows
    expect(event.defaultPrevented).toBe(false);
  });

  it("reloads again once the guard has passed", () => {
    const { fire, reload, advance } = setup();
    fire();
    advance(RELOAD_GUARD_MS);

    fire();

    expect(reload).toHaveBeenCalledTimes(2);
  });

  it("still reloads when storage is unavailable", () => {
    const target = new EventTarget();
    const reload = vi.fn();
    installStaleChunkReload({
      target,
      storage: undefined,
      reload,
      now: () => 0,
    });

    target.dispatchEvent(new Event("vite:preloadError", { cancelable: true }));

    expect(reload).toHaveBeenCalledTimes(1);
  });
});
