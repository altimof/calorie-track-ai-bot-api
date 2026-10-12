import { describe, it, expect } from "vitest";
import { eachDate, getDateRange, parseLocalDate } from "../date";

describe("parseLocalDate", () => {
  it("parses a calendar date as local midnight, not UTC", () => {
    const d = parseLocalDate("2026-10-11");
    expect([d.getFullYear(), d.getMonth(), d.getDate(), d.getHours()]).toEqual([
      2026, 9, 11, 0,
    ]);
  });
});

describe("eachDate", () => {
  it("lists every date from start up to, not including, end", () => {
    expect(eachDate("2026-10-09", "2026-10-12")).toEqual([
      "2026-10-09",
      "2026-10-10",
      "2026-10-11",
    ]);
  });

  it("crosses month and year boundaries", () => {
    expect(eachDate("2026-12-30", "2027-01-02")).toEqual([
      "2026-12-30",
      "2026-12-31",
      "2027-01-01",
    ]);
  });

  it("returns nothing for an empty range", () => {
    expect(eachDate("2026-10-11", "2026-10-11")).toEqual([]);
  });

  it("matches the statistics period length", () => {
    const { start_date, end_date } = getDateRange(90, new Date(2026, 9, 11));
    expect(eachDate(start_date, end_date)).toHaveLength(90);
  });
});

describe("getDateRange", () => {
  // The statistics API treats end_date as exclusive.
  it("includes today by ending the range tomorrow", () => {
    const now = new Date(2026, 9, 11, 15, 30);
    expect(getDateRange(7, now)).toEqual({
      start_date: "2026-10-05",
      end_date: "2026-10-12",
    });
  });

  it("covers exactly the requested number of days", () => {
    const now = new Date(2026, 9, 11);
    const { start_date, end_date } = getDateRange(30, now);
    const days =
      (new Date(end_date).getTime() - new Date(start_date).getTime()) /
      86_400_000;
    expect(days).toBe(30);
  });

  it("handles month and year boundaries", () => {
    expect(getDateRange(7, new Date(2026, 11, 31))).toEqual({
      start_date: "2026-12-25",
      end_date: "2027-01-01",
    });
  });
});
