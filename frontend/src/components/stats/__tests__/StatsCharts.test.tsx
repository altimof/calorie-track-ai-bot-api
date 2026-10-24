import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "@/test/utils";
import i18n from "@/i18n";
import { StatsCharts } from "../StatsCharts";
import type {
  DailyStatisticsResponse,
  MacroStatisticsResponse,
} from "@/api/model";

const mockDailyStats: DailyStatisticsResponse = {
  data: [
    {
      date: "2026-02-13",
      total_calories: 1800,
      total_protein: 120,
      total_fat: 60,
      total_carbs: 200,
      meal_count: 3,
      goal_calories: 2000,
      goal_achievement: 0.9,
    },
    {
      date: "2026-02-14",
      total_calories: 2100,
      total_protein: 130,
      total_fat: 70,
      total_carbs: 220,
      meal_count: 4,
      goal_calories: 2000,
      goal_achievement: 1.05,
    },
  ],
  period: {
    start_date: "2026-02-13",
    end_date: "2026-02-14",
    total_days: 2,
  },
  summary: {
    total_meals: 7,
    average_daily_calories: 1950,
    average_goal_achievement: 0.975,
  },
};

const mockMacroStats: MacroStatisticsResponse = {
  protein_percent: 30,
  fat_percent: 25,
  carbs_percent: 45,
  protein_grams: 125,
  fat_grams: 65,
  carbs_grams: 210,
  total_calories: 1950,
  period: {
    start_date: "2026-02-13",
    end_date: "2026-02-14",
    total_days: 2,
  },
};

describe("StatsCharts", () => {
  it("renders summary stats", () => {
    renderWithProviders(
      <StatsCharts dailyStats={mockDailyStats} macroStats={mockMacroStats} />,
    );
    expect(screen.getByText(/1950/)).toBeInTheDocument();
    expect(screen.getByText(/7/)).toBeInTheDocument();
  });

  it("rounds macro grams and percentages to two decimals", () => {
    renderWithProviders(
      <StatsCharts
        dailyStats={mockDailyStats}
        macroStats={{
          ...mockMacroStats,
          protein_percent: 17.599999999999998,
          fat_percent: 54,
          carbs_percent: 29.123456,
          protein_grams: 55.000000001,
        }}
      />,
    );
    expect(screen.getByText(/55g \(17\.6%\)/)).toBeInTheDocument();
    expect(screen.getByText(/65g \(54%\)/)).toBeInTheDocument();
    expect(screen.getByText(/210g \(29\.12%\)/)).toBeInTheDocument();
  });

  it("keeps up to two decimals on every gram value", () => {
    renderWithProviders(
      <StatsCharts
        dailyStats={mockDailyStats}
        macroStats={{
          ...mockMacroStats,
          protein_grams: 55.555,
          fat_grams: 65.1,
          carbs_grams: 210.005,
        }}
      />,
    );
    expect(screen.getByText(/55\.56g \(30%\)/)).toBeInTheDocument();
    expect(screen.getByText(/65\.1g \(25%\)/)).toBeInTheDocument();
    expect(screen.getByText(/210\.01g \(45%\)/)).toBeInTheDocument();
  });

  it("uses the Russian decimal separator and unit", async () => {
    // TelegramProvider (when present) sets the language from the Telegram user
    const user = window.Telegram!.WebApp.initDataUnsafe.user!;
    user.language_code = "ru";
    await i18n.changeLanguage("ru");
    try {
      renderWithProviders(
        <StatsCharts
          dailyStats={mockDailyStats}
          macroStats={{
            ...mockMacroStats,
            protein_grams: 55.555,
            protein_percent: 17.599999999999998,
          }}
        />,
      );
      expect(screen.getByText(/55,56 г \(17,6%\)/)).toBeInTheDocument();
    } finally {
      user.language_code = "en";
      await i18n.changeLanguage("en");
    }
  });

  it("renders empty state when no data", () => {
    const emptyDaily: DailyStatisticsResponse = {
      data: [],
      period: {
        start_date: "2026-02-13",
        end_date: "2026-02-14",
        total_days: 2,
      },
      summary: {
        total_meals: 0,
        average_daily_calories: 0,
        average_goal_achievement: null,
      },
    };
    renderWithProviders(
      <StatsCharts dailyStats={emptyDaily} macroStats={null} />,
    );
    expect(screen.getByText(/no data/i)).toBeInTheDocument();
  });
});
