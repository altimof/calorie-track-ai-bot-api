import { describe, it, expect, afterEach } from "vitest";
import { act, renderHook } from "@testing-library/react";
import { ApiError } from "../client";
import {
  isNotRegisteredError,
  markNotRegistered,
  resetNotRegistered,
  shouldRetry,
  useNotRegistered,
} from "../registration";

describe("isNotRegisteredError", () => {
  it("matches the backend's 403 for unregistered users", () => {
    expect(isNotRegisteredError(new ApiError(403, "User not registered"))).toBe(
      true,
    );
  });

  it("ignores other errors", () => {
    expect(isNotRegisteredError(new ApiError(403, "Forbidden"))).toBe(false);
    expect(isNotRegisteredError(new ApiError(401, "User not registered"))).toBe(
      false,
    );
    expect(isNotRegisteredError(new Error("User not registered"))).toBe(false);
  });
});

describe("shouldRetry", () => {
  it("does not retry auth failures", () => {
    expect(shouldRetry(0, new ApiError(401, "Missing Telegram initData"))).toBe(
      false,
    );
    expect(shouldRetry(0, new ApiError(403, "User not registered"))).toBe(
      false,
    );
  });

  it("retries other failures once", () => {
    expect(shouldRetry(0, new ApiError(500, "Internal server error"))).toBe(
      true,
    );
    expect(shouldRetry(1, new ApiError(500, "Internal server error"))).toBe(
      false,
    );
  });
});

describe("useNotRegistered", () => {
  afterEach(() => resetNotRegistered());

  it("turns true once a request is rejected as not registered", () => {
    const { result } = renderHook(() => useNotRegistered());
    expect(result.current).toBe(false);

    act(() => markNotRegistered());

    expect(result.current).toBe(true);
  });
});
