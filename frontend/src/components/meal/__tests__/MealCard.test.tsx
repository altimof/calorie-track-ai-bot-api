import { describe, it, expect, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/utils";
import { MealCard } from "../MealCard";
import type { MealWithPhotos } from "@/api/model";

const mockMeal: MealWithPhotos = {
  id: "meal-1",
  userId: "user-1",
  createdAt: "2026-02-15T12:30:00Z",
  description: "Grilled chicken with rice",
  calories: 450,
  macronutrients: { protein: 35, carbs: 40, fats: 12 },
  photos: [
    {
      id: "p1",
      thumbnailUrl: "https://example.com/thumb.jpg",
      fullUrl: "https://example.com/full.jpg",
      displayOrder: 0,
    },
  ],
  confidenceScore: 0.85,
};

describe("MealCard", () => {
  it("renders description and calories", () => {
    renderWithProviders(
      <MealCard meal={mockMeal} onEdit={vi.fn()} onDelete={vi.fn()} />,
    );
    expect(screen.getByText("Grilled chicken with rice")).toBeInTheDocument();
    expect(screen.getByText(/450/)).toBeInTheDocument();
  });

  it("renders macros", () => {
    renderWithProviders(
      <MealCard meal={mockMeal} onEdit={vi.fn()} onDelete={vi.fn()} />,
    );
    expect(screen.getByText(/P: 35g/)).toBeInTheDocument();
    expect(screen.getByText(/C: 40g/)).toBeInTheDocument();
    expect(screen.getByText(/F: 12g/)).toBeInTheDocument();
  });

  it("rounds macros to two decimals", () => {
    renderWithProviders(
      <MealCard
        meal={{
          ...mockMeal,
          macronutrients: {
            protein: 35.555,
            carbs: 0.1 + 0.2,
            fats: 12.000000001,
          },
        }}
        onEdit={vi.fn()}
        onDelete={vi.fn()}
      />,
    );
    expect(screen.getByText("P: 35.56g")).toBeInTheDocument();
    expect(screen.getByText("C: 0.3g")).toBeInTheDocument();
    expect(screen.getByText("F: 12g")).toBeInTheDocument();
  });

  it("shows thumbnail when photo exists", () => {
    renderWithProviders(
      <MealCard meal={mockMeal} onEdit={vi.fn()} onDelete={vi.fn()} />,
    );
    const img = screen.getByRole("img");
    expect(img).toHaveAttribute("src", "https://example.com/thumb.jpg");
  });

  it("calls onEdit when edit button clicked", async () => {
    const onEdit = vi.fn();
    renderWithProviders(
      <MealCard meal={mockMeal} onEdit={onEdit} onDelete={vi.fn()} />,
    );
    await userEvent.click(screen.getByLabelText(/edit/i));
    expect(onEdit).toHaveBeenCalledWith("meal-1");
  });

  it("calls onDelete when delete button clicked", async () => {
    const onDelete = vi.fn();
    renderWithProviders(
      <MealCard meal={mockMeal} onEdit={vi.fn()} onDelete={onDelete} />,
    );
    await userEvent.click(screen.getByLabelText(/delete/i));
    expect(onDelete).toHaveBeenCalledWith("meal-1");
  });
});
