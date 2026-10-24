import { useTranslation } from "react-i18next";
import type { MealWithPhotos } from "@/api/model";
import { formatDecimal } from "@/utils/number";

interface MealCardProps {
  meal: MealWithPhotos;
  onEdit: (id: string) => void;
  onDelete: (id: string) => void;
}

function formatTime(dateString: string): string {
  return new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(dateString));
}

export function MealCard({ meal, onEdit, onDelete }: MealCardProps) {
  const { t, i18n } = useTranslation();
  const formatGrams = (value: number) =>
    t("common.grams", { value: formatDecimal(value, i18n.language) });
  const thumbnail = meal.photos?.[0]?.thumbnailUrl;

  return (
    <div className="flex gap-3 rounded-xl bg-tg-secondary-bg p-3">
      {thumbnail && (
        <img
          src={thumbnail}
          alt={meal.description ?? ""}
          className="h-16 w-16 shrink-0 rounded-lg object-cover"
        />
      )}
      <div className="flex flex-1 flex-col gap-1">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-sm font-medium text-tg-text">
              {meal.description ?? t("meals.list.empty")}
            </p>
            <p className="text-xs text-tg-hint">{formatTime(meal.createdAt)}</p>
          </div>
          <span className="text-sm font-semibold text-tg-text">
            {meal.calories} kcal
          </span>
        </div>
        <div className="flex items-center gap-2 text-xs text-tg-hint">
          <span>P: {formatGrams(meal.macronutrients.protein)}</span>
          <span>C: {formatGrams(meal.macronutrients.carbs)}</span>
          <span>F: {formatGrams(meal.macronutrients.fats)}</span>
        </div>
        <div className="flex justify-end gap-2">
          <button
            type="button"
            aria-label={t("mealDetail.edit")}
            onClick={() => onEdit(meal.id)}
            className="rounded p-1 text-xs text-tg-link hover:bg-tg-bg"
          >
            {t("mealDetail.edit")}
          </button>
          <button
            type="button"
            aria-label={t("mealDetail.delete")}
            onClick={() => onDelete(meal.id)}
            className="rounded p-1 text-xs text-red-500 hover:bg-tg-bg"
          >
            {t("mealDetail.delete")}
          </button>
        </div>
      </div>
    </div>
  );
}
