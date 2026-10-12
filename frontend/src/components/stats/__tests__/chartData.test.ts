import { describe, it, expect } from "vitest";
import { dailyCalories } from "../chartData";
import type { DailyStatisticsResponse } from "@/api/model";

const stats: DailyStatisticsResponse = {
  data: [
    {
      date: "2026-10-07",
      total_calories: 1745,
      total_protein: 80,
      total_fat: 107,
      total_carbs: 120,
      meal_count: 1,
      goal_calories: 2000,
      goal_achievement: 87.25,
    },
    {
      date: "2026-10-11",
      total_calories: 495,
      total_protein: 30,
      total_fat: 20,
      total_carbs: 50,
      meal_count: 1,
      goal_calories: 2000,
      goal_achievement: 24.75,
    },
  ],
  period: { start_date: "2026-10-05", end_date: "2026-10-12", total_days: 7 },
  summary: {
    total_meals: 2,
    average_daily_calories: 320,
    average_goal_achievement: 56,
  },
};

describe("dailyCalories", () => {
  it("has one entry per day of the period, with 0 for days without meals", () => {
    expect(dailyCalories(stats)).toEqual([
      { date: "2026-10-05", total_calories: 0 },
      { date: "2026-10-06", total_calories: 0 },
      { date: "2026-10-07", total_calories: 1745 },
      { date: "2026-10-08", total_calories: 0 },
      { date: "2026-10-09", total_calories: 0 },
      { date: "2026-10-10", total_calories: 0 },
      { date: "2026-10-11", total_calories: 495 },
    ]);
  });

  it("returns all zeros when there were no meals", () => {
    const entries = dailyCalories({ ...stats, data: [] });
    expect(entries).toHaveLength(7);
    expect(entries.every((e) => e.total_calories === 0)).toBe(true);
  });
});
