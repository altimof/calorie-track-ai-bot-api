import { describe, it, expect, vi, beforeEach } from "vitest";
import { customFetch, ApiError } from "../client";

describe("customFetch", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("sends Telegram initData as Authorization and no x-user-id", async () => {
    const spy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(
        new Response(JSON.stringify({ ok: true }), { status: 200 }),
      );

    await customFetch({ url: "/health/live", method: "GET" });

    const [, init] = spy.mock.calls[0];
    const headers = init?.headers as Record<string, string>;
    expect(headers["Authorization"]).toBe("tma mock_init_data");
    expect(headers["x-user-id"]).toBeUndefined();
  });

  it("falls back to dev x-user-id without initData in dev builds", async () => {
    const webapp = window.Telegram!.WebApp;
    const original = webapp.initData;
    webapp.initData = "";
    try {
      const spy = vi
        .spyOn(globalThis, "fetch")
        .mockResolvedValue(
          new Response(JSON.stringify({ ok: true }), { status: 200 }),
        );

      await customFetch({ url: "/health/live", method: "GET" });

      const [, init] = spy.mock.calls[0];
      const headers = init?.headers as Record<string, string>;
      expect(headers["Authorization"]).toBeUndefined();
      expect(headers["x-user-id"]).toBe(
        import.meta.env.VITE_DEV_USER_ID ?? "59357664",
      );
    } finally {
      webapp.initData = original;
    }
  });

  it("adds X-Correlation-ID header", async () => {
    const spy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(
        new Response(JSON.stringify({ ok: true }), { status: 200 }),
      );

    await customFetch({ url: "/health/live", method: "GET" });

    const [, init] = spy.mock.calls[0];
    expect(
      (init?.headers as Record<string, string>)["X-Correlation-ID"],
    ).toBeDefined();
  });

  it("adds X-Timezone header with the browser's IANA time zone", async () => {
    const spy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(
        new Response(JSON.stringify({ ok: true }), { status: 200 }),
      );

    await customFetch({ url: "/health/live", method: "GET" });

    const [, init] = spy.mock.calls[0];
    expect((init?.headers as Record<string, string>)["X-Timezone"]).toBe(
      Intl.DateTimeFormat().resolvedOptions().timeZone,
    );
  });

  it("throws ApiError on non-ok response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "Not found" }), { status: 404 }),
    );

    await expect(
      customFetch({ url: "/api/v1/meals/unknown", method: "GET" }),
    ).rejects.toThrow(ApiError);
  });

  it("returns undefined for 204 responses", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(null, { status: 204 }),
    );

    const result = await customFetch({
      url: "/api/v1/meals/1",
      method: "DELETE",
    });
    expect(result).toBeUndefined();
  });
});

describe("customFetch session expiry", () => {
  const webapp = window.Telegram!.WebApp;

  // A fresh module each time, so the alert can be shown again
  async function loadClient() {
    vi.resetModules();
    return import("../client");
  }

  function respond(status: number, detail: string) {
    return vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify({ detail }), { status }));
  }

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("asks to reopen the app and closes it when signed initData is rejected", async () => {
    const { customFetch, ApiError } = await loadClient();
    const showAlert = vi
      .spyOn(webapp, "showAlert")
      .mockImplementation((_message, callback) => callback?.());
    const close = vi.spyOn(webapp, "close");
    respond(401, "Invalid Telegram initData");

    await expect(
      customFetch({ url: "/api/v1/goals", method: "GET" }),
    ).rejects.toThrow(ApiError);

    expect(showAlert).toHaveBeenCalledTimes(1);
    expect(showAlert.mock.calls[0][0]).toMatch(/reopen the app/);
    expect(close).toHaveBeenCalledTimes(1);
  });

  it("shows the alert only once when several requests fail", async () => {
    const { customFetch } = await loadClient();
    const showAlert = vi.spyOn(webapp, "showAlert");
    respond(401, "Invalid Telegram initData");

    await Promise.allSettled([
      customFetch({ url: "/api/v1/goals", method: "GET" }),
      customFetch({ url: "/api/v1/meals", method: "GET" }),
    ]);

    expect(showAlert).toHaveBeenCalledTimes(1);
  });

  it("does not alert on other errors", async () => {
    const { customFetch } = await loadClient();
    const showAlert = vi.spyOn(webapp, "showAlert");
    respond(403, "User not registered");

    await customFetch({ url: "/api/v1/goals", method: "GET" }).catch(() => {});

    expect(showAlert).not.toHaveBeenCalled();
  });

  it("does not alert on a 401 without initData (dev builds)", async () => {
    const { customFetch } = await loadClient();
    const showAlert = vi.spyOn(webapp, "showAlert");
    const original = webapp.initData;
    webapp.initData = "";
    try {
      respond(401, "Missing Telegram initData");
      await customFetch({ url: "/api/v1/goals", method: "GET" }).catch(
        () => {},
      );
      expect(showAlert).not.toHaveBeenCalled();
    } finally {
      webapp.initData = original;
    }
  });
});
