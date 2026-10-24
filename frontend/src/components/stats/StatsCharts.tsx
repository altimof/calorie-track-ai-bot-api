import { useTranslation } from "react-i18next";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
  PieChart,
  Pie,
  Cell,
} from "recharts";
import type {
  DailyStatisticsResponse,
  MacroStatisticsResponse,
} from "@/api/model";
import { parseLocalDate } from "@/utils/date";
import { dailyCalories } from "./chartData";
import { formatDecimal } from "@/utils/number";

interface StatsChartsProps {
  dailyStats: DailyStatisticsResponse;
  macroStats: MacroStatisticsResponse | null;
}

const MACRO_COLORS = ["#4CAF50", "#FF9800", "#2196F3"];

function formatChartDate(date: string, language: string): string {
  return parseLocalDate(date).toLocaleDateString(language, {
    month: "short",
    day: "numeric",
  });
}

export function StatsCharts({ dailyStats, macroStats }: StatsChartsProps) {
  const { t, i18n } = useTranslation();
  const formatNumber = (value: number) => formatDecimal(value, i18n.language);
  const formatDate = (date: string) => formatChartDate(date, i18n.language);
  const formatGrams = (value: number) =>
    t("common.grams", { value: formatNumber(value) });

  if (dailyStats.data.length === 0) {
    return (
      <div className="flex flex-col items-center gap-2 py-12 text-center">
        <p className="text-lg font-medium text-tg-text">
          {t("statistics.emptyState.title")}
        </p>
        <p className="text-sm text-tg-hint">
          {t("statistics.emptyState.message")}
        </p>
      </div>
    );
  }

  const { summary } = dailyStats;
  const chartData = dailyCalories(dailyStats);
  const goalCalories = dailyStats.data.find(
    (day) => day.goal_calories,
  )?.goal_calories;

  return (
    <div className="flex flex-col gap-4">
      {/* Summary cards */}
      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-xl bg-tg-secondary-bg p-4 text-center">
          <p className="text-2xl font-bold text-tg-text">
            {Math.round(summary.average_daily_calories)}
          </p>
          <p className="text-xs text-tg-hint">
            {t("statistics.summary.avgDaily")}
          </p>
        </div>
        <div className="rounded-xl bg-tg-secondary-bg p-4 text-center">
          <p className="text-2xl font-bold text-tg-text">
            {summary.total_meals}
          </p>
          <p className="text-xs text-tg-hint">
            {t("statistics.summary.totalMeals")}
          </p>
        </div>
      </div>

      {/* Daily calories bar chart */}
      <div>
        <h3 className="mb-2 text-sm font-medium text-tg-text">
          {t("statistics.caloriesOverTime")}
        </h3>
        <ResponsiveContainer width="100%" height={160}>
          <BarChart data={chartData}>
            <XAxis
              dataKey="date"
              tickFormatter={formatDate}
              tick={{ fontSize: 10 }}
            />
            <YAxis tick={{ fontSize: 10 }} />
            <Tooltip
              labelFormatter={(date) => formatDate(String(date))}
              formatter={(kcal) => [
                formatNumber(Math.round(Number(kcal))),
                t("statistics.chart.calories"),
              ]}
            />
            <Bar
              dataKey="total_calories"
              fill="var(--color-tg-button)"
              radius={[3, 3, 0, 0]}
            />
            {goalCalories && (
              <ReferenceLine
                y={goalCalories}
                stroke="var(--color-tg-hint)"
                strokeDasharray="4 4"
                ifOverflow="extendDomain"
              />
            )}
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Macro pie chart */}
      {macroStats && (
        <div>
          <h3 className="mb-2 text-sm font-medium text-tg-text">
            {t("statistics.macroBreakdown")}
          </h3>
          <div className="flex items-center gap-4">
            <ResponsiveContainer width={120} height={120}>
              <PieChart>
                <Pie
                  data={[
                    {
                      name: t("statistics.chart.protein"),
                      value: macroStats.protein_percent,
                    },
                    {
                      name: t("statistics.chart.fat"),
                      value: macroStats.fat_percent,
                    },
                    {
                      name: t("statistics.chart.carbs"),
                      value: macroStats.carbs_percent,
                    },
                  ]}
                  innerRadius={30}
                  outerRadius={50}
                  dataKey="value"
                >
                  {MACRO_COLORS.map((color, i) => (
                    <Cell key={i} fill={color} />
                  ))}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
            <div className="flex flex-col gap-1 text-sm">
              <span style={{ color: MACRO_COLORS[0] }}>
                {t("statistics.chart.protein")}:{" "}
                {formatGrams(macroStats.protein_grams)} (
                {formatNumber(macroStats.protein_percent)}%)
              </span>
              <span style={{ color: MACRO_COLORS[1] }}>
                {t("statistics.chart.fat")}: {formatGrams(macroStats.fat_grams)}{" "}
                ({formatNumber(macroStats.fat_percent)}%)
              </span>
              <span style={{ color: MACRO_COLORS[2] }}>
                {t("statistics.chart.carbs")}:{" "}
                {formatGrams(macroStats.carbs_grams)} (
                {formatNumber(macroStats.carbs_percent)}%)
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
