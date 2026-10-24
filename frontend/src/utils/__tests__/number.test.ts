import { describe, it, expect } from "vitest";
import { formatDecimal } from "../number";

describe("formatDecimal", () => {
  it("rounds to at most two decimals and drops trailing zeros", () => {
    expect(formatDecimal(17.599999999999998, "en")).toBe("17.6");
    expect(formatDecimal(29.123456, "en")).toBe("29.12");
    expect(formatDecimal(54, "en")).toBe("54");
    expect(formatDecimal(0.1 + 0.2, "en")).toBe("0.3");
  });

  it("rounds halfway values up, unlike Math.round(x * 100) / 100", () => {
    expect(formatDecimal(1.005, "en")).toBe("1.01");
    expect(formatDecimal(1.015, "en")).toBe("1.02");
  });

  it("uses the language's decimal separator", () => {
    expect(formatDecimal(17.6, "ru")).toBe("17,6");
    expect(formatDecimal(55.555, "ru")).toBe("55,56");
  });
});
