import { useTranslation } from "react-i18next";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  PieChart,
  Pie,
  Cell,
} from "recharts";
import type {
  DailyStatisticsResponse,
  MacroStatisticsResponse,
} from "@/api/model";

interface StatsChartsProps {
  dailyStats: DailyStatisticsResponse;
  macroStats: MacroStatisticsResponse | null;
}

const MACRO_COLORS = ["#4CAF50", "#FF9800", "#2196F3"];

// At most two decimal places, without trailing zeros (17.599999999999998 -> 17.6)
function formatMacroValue(value: number): string {
  return String(Math.round(value * 100) / 100);
}

export function StatsCharts({ dailyStats, macroStats }: StatsChartsProps) {
  const { t } = useTranslation();

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

  return (
    <div className="flex flex-col gap-6">
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

      {/* Calories line chart */}
      <div>
        <h3 className="mb-2 text-sm font-medium text-tg-text">
          {t("statistics.caloriesOverTime")}
        </h3>
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={dailyStats.data}>
            <XAxis
              dataKey="date"
              tickFormatter={(d) =>
                new Date(d).toLocaleDateString(undefined, {
                  month: "short",
                  day: "numeric",
                })
              }
              tick={{ fontSize: 10 }}
            />
            <YAxis tick={{ fontSize: 10 }} />
            <Tooltip />
            <Line
              type="monotone"
              dataKey="total_calories"
              stroke="var(--color-tg-button)"
              strokeWidth={2}
              dot={false}
            />
            <Line
              type="monotone"
              dataKey="goal_calories"
              stroke="var(--color-tg-hint)"
              strokeWidth={1}
              strokeDasharray="4 4"
              dot={false}
            />
          </LineChart>
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
                {formatMacroValue(macroStats.protein_grams)}g (
                {formatMacroValue(macroStats.protein_percent)}%)
              </span>
              <span style={{ color: MACRO_COLORS[1] }}>
                {t("statistics.chart.fat")}:{" "}
                {formatMacroValue(macroStats.fat_grams)}g (
                {formatMacroValue(macroStats.fat_percent)}%)
              </span>
              <span style={{ color: MACRO_COLORS[2] }}>
                {t("statistics.chart.carbs")}:{" "}
                {formatMacroValue(macroStats.carbs_grams)}g (
                {formatMacroValue(macroStats.carbs_percent)}%)
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
