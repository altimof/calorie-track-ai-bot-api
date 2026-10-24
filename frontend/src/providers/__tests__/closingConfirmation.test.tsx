import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook } from "@testing-library/react";
import { TelegramProvider, useClosingConfirmation } from "../telegram";

function wrapper({ children }: { children: React.ReactNode }) {
  return <TelegramProvider>{children}</TelegramProvider>;
}

describe("useClosingConfirmation", () => {
  const webapp = window.Telegram!.WebApp as Required<TelegramWebApp>;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("does nothing while there are no unsaved changes", () => {
    const enable = vi.spyOn(webapp, "enableClosingConfirmation");
    renderHook(() => useClosingConfirmation(false), { wrapper });
    expect(enable).not.toHaveBeenCalled();
  });

  it("enables when dirty and disables once changes are saved", () => {
    const enable = vi.spyOn(webapp, "enableClosingConfirmation");
    const disable = vi.spyOn(webapp, "disableClosingConfirmation");
    const { rerender } = renderHook(
      ({ dirty }) => useClosingConfirmation(dirty),
      { wrapper, initialProps: { dirty: true } },
    );
    expect(enable).toHaveBeenCalledTimes(1);
    expect(disable).not.toHaveBeenCalled();

    rerender({ dirty: false });
    expect(disable).toHaveBeenCalledTimes(1);
  });

  it("disables when a dirty form unmounts", () => {
    const disable = vi.spyOn(webapp, "disableClosingConfirmation");
    const { unmount } = renderHook(() => useClosingConfirmation(true), {
      wrapper,
    });
    unmount();
    expect(disable).toHaveBeenCalledTimes(1);
  });

  it("stays enabled while another form is still dirty", () => {
    const enable = vi.spyOn(webapp, "enableClosingConfirmation");
    const disable = vi.spyOn(webapp, "disableClosingConfirmation");
    const { rerender } = renderHook(
      ({ first, second }) => {
        useClosingConfirmation(first);
        useClosingConfirmation(second);
      },
      { wrapper, initialProps: { first: true, second: true } },
    );
    expect(enable).toHaveBeenCalledTimes(1);

    rerender({ first: false, second: true });
    expect(disable).not.toHaveBeenCalled();

    rerender({ first: false, second: false });
    expect(disable).toHaveBeenCalledTimes(1);
  });

  it("turns on again after being turned off", () => {
    const enable = vi.spyOn(webapp, "enableClosingConfirmation");
    const { rerender } = renderHook(
      ({ dirty }) => useClosingConfirmation(dirty),
      { wrapper, initialProps: { dirty: true } },
    );
    rerender({ dirty: false });
    rerender({ dirty: true });
    expect(enable).toHaveBeenCalledTimes(2);
  });

  it("does nothing outside TelegramProvider", () => {
    const enable = vi.spyOn(webapp, "enableClosingConfirmation");
    renderHook(() => useClosingConfirmation(true));
    expect(enable).not.toHaveBeenCalled();
  });

  it("tolerates Telegram clients without the closing confirmation API", () => {
    const original = webapp.enableClosingConfirmation;
    (webapp as TelegramWebApp).enableClosingConfirmation = undefined;
    try {
      expect(() =>
        renderHook(() => useClosingConfirmation(true), { wrapper }),
      ).not.toThrow();
    } finally {
      webapp.enableClosingConfirmation = original;
    }
  });
});
