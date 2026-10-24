import { describe, it, expect, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/utils";
import { MealEditor } from "../MealEditor";

const defaultMeal = {
  description: "Chicken",
  calories: 450,
  protein: 35,
  carbs: 40,
  fats: 12,
};

describe("MealEditor", () => {
  it("renders form fields pre-filled with data", () => {
    renderWithProviders(
      <MealEditor meal={defaultMeal} onSave={vi.fn()} onCancel={vi.fn()} />,
    );
    expect(screen.getByLabelText(/description/i)).toHaveValue("Chicken");
    expect(screen.getByLabelText(/protein/i)).toHaveValue(35);
    expect(screen.getByLabelText(/carbs/i)).toHaveValue(40);
    expect(screen.getByLabelText(/fat/i)).toHaveValue(12);
  });

  it("calls onSave with updated data", async () => {
    const onSave = vi.fn();
    renderWithProviders(
      <MealEditor meal={defaultMeal} onSave={onSave} onCancel={vi.fn()} />,
    );
    const descInput = screen.getByLabelText(/description/i);
    await userEvent.clear(descInput);
    await userEvent.type(descInput, "Updated meal");
    await userEvent.click(screen.getByRole("button", { name: /save/i }));
    expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({ description: "Updated meal" }),
    );
  });

  it("calls onCancel when cancelled", async () => {
    const onCancel = vi.fn();
    renderWithProviders(
      <MealEditor meal={defaultMeal} onSave={vi.fn()} onCancel={onCancel} />,
    );
    await userEvent.click(screen.getByRole("button", { name: /cancel/i }));
    expect(onCancel).toHaveBeenCalled();
  });

  describe("closing confirmation", () => {
    const webapp = window.Telegram!.WebApp as Required<TelegramWebApp>;

    it("warns while a field differs and stops when it is typed back", async () => {
      const enable = vi.spyOn(webapp, "enableClosingConfirmation");
      const disable = vi.spyOn(webapp, "disableClosingConfirmation");
      renderWithProviders(
        <MealEditor meal={defaultMeal} onSave={vi.fn()} onCancel={vi.fn()} />,
      );
      const protein = screen.getByLabelText(/protein/i);

      await userEvent.clear(protein);
      await userEvent.type(protein, "50");
      expect(enable).toHaveBeenCalledTimes(1);

      // Calories are recalculated from the macros (408, not the original 450),
      // but every field the user can edit matches again
      await userEvent.clear(protein);
      await userEvent.type(protein, "35");
      expect(disable).toHaveBeenCalledTimes(1);
      enable.mockRestore();
      disable.mockRestore();
    });

    it("stops warning when the editor closes", async () => {
      const disable = vi.spyOn(webapp, "disableClosingConfirmation");
      const { unmount } = renderWithProviders(
        <MealEditor meal={defaultMeal} onSave={vi.fn()} onCancel={vi.fn()} />,
      );
      await userEvent.type(screen.getByLabelText(/description/i), " salad");
      unmount();
      expect(disable).toHaveBeenCalledTimes(1);
      disable.mockRestore();
    });
  });
});
