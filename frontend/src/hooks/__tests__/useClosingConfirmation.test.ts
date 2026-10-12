import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook } from "@testing-library/react";
import { useClosingConfirmation } from "../useClosingConfirmation";

describe("useClosingConfirmation", () => {
  const webapp = window.Telegram!.WebApp;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("does nothing while there are no unsaved changes", () => {
    const enable = vi.spyOn(webapp, "enableClosingConfirmation");
    renderHook(() => useClosingConfirmation(false));
    expect(enable).not.toHaveBeenCalled();
  });

  it("enables when dirty and disables once changes are saved", () => {
    const enable = vi.spyOn(webapp, "enableClosingConfirmation");
    const disable = vi.spyOn(webapp, "disableClosingConfirmation");
    const { rerender } = renderHook(
      ({ dirty }) => useClosingConfirmation(dirty),
      { initialProps: { dirty: true } },
    );
    expect(enable).toHaveBeenCalledTimes(1);
    expect(disable).not.toHaveBeenCalled();

    rerender({ dirty: false });
    expect(disable).toHaveBeenCalledTimes(1);
  });

  it("disables when a dirty form unmounts", () => {
    const disable = vi.spyOn(webapp, "disableClosingConfirmation");
    const { unmount } = renderHook(() => useClosingConfirmation(true));
    unmount();
    expect(disable).toHaveBeenCalledTimes(1);
  });

  it("stays enabled while another form is still dirty", () => {
    const enable = vi.spyOn(webapp, "enableClosingConfirmation");
    const disable = vi.spyOn(webapp, "disableClosingConfirmation");
    const first = renderHook(() => useClosingConfirmation(true));
    const second = renderHook(() => useClosingConfirmation(true));
    expect(enable).toHaveBeenCalledTimes(1);

    first.unmount();
    expect(disable).not.toHaveBeenCalled();

    second.unmount();
    expect(disable).toHaveBeenCalledTimes(1);
  });
});
