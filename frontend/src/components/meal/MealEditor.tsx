import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useClosingConfirmation } from "@/providers/telegram";

interface MealFormData {
  description: string;
  calories: number;
  protein: number;
  carbs: number;
  fats: number;
}

interface MealEditorProps {
  meal: MealFormData;
  onSave: (data: MealFormData) => void;
  onCancel: () => void;
  saving?: boolean;
}

export type { MealFormData };

const EDITABLE_FIELDS = ["description", "protein", "carbs", "fats"] as const;

export function MealEditor({
  meal,
  onSave,
  onCancel,
  saving,
}: MealEditorProps) {
  const { t } = useTranslation();
  const [form, setForm] = useState<MealFormData>(meal);
  // Only the fields the user types into: calories is recalculated from the macros
  // and rarely equals the AI's original value, so it would stay "changed".
  useClosingConfirmation(
    EDITABLE_FIELDS.some((field) => form[field] !== meal[field]),
  );

  const handleChange = (field: keyof MealFormData, value: string) => {
    setForm((prev) => {
      const updated = {
        ...prev,
        [field]: field === "description" ? value : Number(value) || 0,
      };
      if (field !== "description" && field !== "calories") {
        updated.calories = Math.round(
          updated.protein * 4 + updated.carbs * 4 + updated.fats * 9,
        );
      }
      return updated;
    });
  };

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        onSave(form);
      }}
      className="flex flex-col gap-4"
    >
      <label className="flex flex-col gap-1">
        <span className="text-sm text-tg-hint">
          {t("mealDetail.description")}
        </span>
        <input
          aria-label={t("mealDetail.description")}
          type="text"
          value={form.description}
          onChange={(e) => handleChange("description", e.target.value)}
          className="rounded-lg border border-tg-hint/30 bg-tg-secondary-bg px-3 py-2 text-tg-text"
        />
      </label>
      <div className="grid grid-cols-3 gap-3">
        <label className="flex flex-col gap-1">
          <span className="text-sm text-tg-hint">
            {t("today.macros.protein")}
          </span>
          <input
            aria-label={t("mealDetail.protein")}
            type="number"
            min={0}
            value={form.protein}
            onChange={(e) => handleChange("protein", e.target.value)}
            className="rounded-lg border border-tg-hint/30 bg-tg-secondary-bg px-3 py-2 text-tg-text"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-sm text-tg-hint">
            {t("today.macros.carbs")}
          </span>
          <input
            aria-label={t("mealDetail.carbs")}
            type="number"
            min={0}
            value={form.carbs}
            onChange={(e) => handleChange("carbs", e.target.value)}
            className="rounded-lg border border-tg-hint/30 bg-tg-secondary-bg px-3 py-2 text-tg-text"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-sm text-tg-hint">{t("today.macros.fat")}</span>
          <input
            aria-label={t("mealDetail.fat")}
            type="number"
            min={0}
            value={form.fats}
            onChange={(e) => handleChange("fats", e.target.value)}
            className="rounded-lg border border-tg-hint/30 bg-tg-secondary-bg px-3 py-2 text-tg-text"
          />
        </label>
      </div>
      <p className="text-center text-sm text-tg-hint">{form.calories} kcal</p>
      <div className="flex gap-3">
        <button
          type="button"
          onClick={onCancel}
          className="flex-1 rounded-lg border border-tg-hint/30 py-2 text-sm text-tg-text"
        >
          {t("mealDetail.cancel")}
        </button>
        <button
          type="submit"
          disabled={saving}
          className="flex-1 rounded-lg bg-tg-button py-2 text-sm font-medium text-tg-button-text disabled:opacity-50"
        >
          {saving ? t("mealDetail.saving") : t("mealDetail.save")}
        </button>
      </div>
    </form>
  );
}
