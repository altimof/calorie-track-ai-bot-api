import type { DailyStatisticsResponse } from "@/api/model";
import { eachDate } from "@/utils/date";

/**
 * Calories for every day of the statistics period, oldest first. The API only
 * returns days that had meals; the others are filled in with 0.
 */
export function dailyCalories(dailyStats: DailyStatisticsResponse) {
  const byDate = new Map(
    dailyStats.data.map((day) => [day.date, day.total_calories]),
  );
  return eachDate(dailyStats.period.start_date, dailyStats.period.end_date).map(
    (date) => ({ date, total_calories: byDate.get(date) ?? 0 }),
  );
}
