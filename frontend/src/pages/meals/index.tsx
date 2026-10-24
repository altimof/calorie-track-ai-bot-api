import { useState, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { useQueryClient } from "@tanstack/react-query";
import {
  useGetMealsApiV1MealsGet,
  useUpdateMealApiV1MealsMealIdPatch,
  useDeleteMealApiV1MealsMealIdDelete,
} from "@/api/queries/meals/meals";
import { useGetDailySummaryApiV1DailySummaryDateGet } from "@/api/queries/daily-summary/daily-summary";
import { useGetGoalApiV1GoalsGet } from "@/api/queries/goals/goals";
import { MealCard } from "@/components/meal/MealCard";
import { MealEditor } from "@/components/meal/MealEditor";
import type { MealFormData } from "@/components/meal/MealEditor";
import { Modal } from "@/components/ui/Modal";
import { Skeleton } from "@/components/ui/Skeleton";
import { unwrap } from "@/api/unwrap";
import { formatDate } from "@/utils/date";
import { formatDecimal } from "@/utils/number";
import type { MealWithPhotos } from "@/api/model";
import type { MealsListResponse } from "@/api/model";
import type { DailySummary } from "@/api/model";
import type { GoalResponse } from "@/api/model";

export default function MealsPage() {
  const { t, i18n } = useTranslation();
  const formatGrams = (value: number) =>
    t("common.grams", { value: formatDecimal(value, i18n.language) });
  const queryClient = useQueryClient();
  const [selectedDate] = useState(formatDate(new Date()));
  const [editingMeal, setEditingMeal] = useState<MealWithPhotos | null>(null);
  const [deletingMealId, setDeletingMealId] = useState<string | null>(null);
  const [mutationError, setMutationError] = useState<string | null>(null);

  const { data: mealsRaw, isLoading } = useGetMealsApiV1MealsGet({
    date: selectedDate,
  });
  const { data: summaryRaw } =
    useGetDailySummaryApiV1DailySummaryDateGet(selectedDate);
  const { data: goalRaw } = useGetGoalApiV1GoalsGet();
  const updateMeal = useUpdateMealApiV1MealsMealIdPatch();
  const deleteMeal = useDeleteMealApiV1MealsMealIdDelete();

  const mealsData = unwrap<MealsListResponse>(mealsRaw);
  const summary = unwrap<DailySummary>(summaryRaw);
  const goal = unwrap<GoalResponse>(goalRaw);

  const invalidateAll = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ["/api/v1/meals"] });
    queryClient.invalidateQueries({ queryKey: ["/api/v1/daily-summary"] });
  }, [queryClient]);

  const handleEdit = useCallback(
    (id: string) => {
      const meal = mealsData?.meals.find((m) => m.id === id);
      if (meal) {
        setMutationError(null);
        setEditingMeal(meal);
      }
    },
    [mealsData],
  );

  const handleDelete = useCallback((id: string) => {
    setMutationError(null);
    setDeletingMealId(id);
  }, []);

  const confirmDelete = useCallback(() => {
    if (!deletingMealId) return;
    deleteMeal.mutate(
      { mealId: deletingMealId },
      {
        onSuccess: () => {
          setDeletingMealId(null);
          invalidateAll();
        },
        onError: () => {
          setDeletingMealId(null);
          setMutationError(t("mealDetail.deleteError"));
        },
      },
    );
  }, [deletingMealId, deleteMeal, invalidateAll, t]);

  const handleSave = useCallback(
    (data: MealFormData) => {
      if (!editingMeal) return;
      updateMeal.mutate(
        {
          mealId: editingMeal.id,
          data: {
            description: data.description,
            protein_grams: data.protein,
            carbs_grams: data.carbs,
            fats_grams: data.fats,
          },
        },
        {
          onSuccess: () => {
            setEditingMeal(null);
            invalidateAll();
          },
          onError: () => {
            setMutationError(t("mealDetail.saveError"));
          },
        },
      );
    },
    [editingMeal, updateMeal, invalidateAll, t],
  );

  return (
    <div className="flex flex-col gap-4 p-4">
      <h1 className="text-lg font-semibold text-tg-text">{t("meals.title")}</h1>

      {/* Error banner */}
      {mutationError && (
        <div className="rounded-lg bg-red-500/10 px-4 py-2 text-sm text-red-500">
          {mutationError}
        </div>
      )}

      {/* Daily summary */}
      {summary && (
        <div className="flex items-center justify-between rounded-xl bg-tg-secondary-bg p-4">
          <div>
            <p className="text-2xl font-bold text-tg-text">
              {summary.kcal_total} kcal
            </p>
            {goal && (
              <p className="text-sm text-tg-hint">
                {t("meals.summary.goal", {
                  target: goal.daily_kcal_target,
                })}
              </p>
            )}
          </div>
          <div className="flex gap-4 text-xs text-tg-hint">
            <span>
              {t("today.macros.protein")}:{" "}
              {formatGrams(summary.macros_totals.protein_g)}
            </span>
            <span>
              {t("today.macros.fat")}:{" "}
              {formatGrams(summary.macros_totals.fat_g)}
            </span>
            <span>
              {t("today.macros.carbs")}:{" "}
              {formatGrams(summary.macros_totals.carbs_g)}
            </span>
          </div>
        </div>
      )}

      {/* Meal list */}
      {isLoading ? (
        <div className="flex flex-col gap-3">
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-20 w-full" />
        </div>
      ) : mealsData?.meals.length ? (
        <div className="flex flex-col gap-3">
          {mealsData.meals.map((meal) => (
            <MealCard
              key={meal.id}
              meal={meal}
              onEdit={handleEdit}
              onDelete={handleDelete}
            />
          ))}
        </div>
      ) : (
        <p className="py-8 text-center text-sm text-tg-hint">
          {t("meals.list.empty")}
        </p>
      )}

      {/* Delete confirmation modal */}
      <Modal
        open={!!deletingMealId}
        onClose={() => setDeletingMealId(null)}
        title={t("mealDetail.deleteMeal")}
      >
        <div className="flex flex-col gap-4">
          <p className="text-sm text-tg-text">
            {t("mealDetail.deleteConfirm")}
          </p>
          <div className="flex gap-3">
            <button
              type="button"
              onClick={() => setDeletingMealId(null)}
              className="flex-1 rounded-lg border border-tg-hint/30 py-2 text-sm text-tg-text"
            >
              {t("mealDetail.cancel")}
            </button>
            <button
              type="button"
              onClick={confirmDelete}
              disabled={deleteMeal.isPending}
              className="flex-1 rounded-lg bg-red-500 py-2 text-sm font-medium text-white disabled:opacity-50"
            >
              {deleteMeal.isPending
                ? t("mealDetail.saving")
                : t("mealDetail.confirmDelete")}
            </button>
          </div>
        </div>
      </Modal>

      {/* Edit modal */}
      <Modal
        open={!!editingMeal}
        onClose={() => setEditingMeal(null)}
        title={t("mealDetail.edit")}
      >
        {editingMeal && (
          <MealEditor
            meal={{
              description: editingMeal.description ?? "",
              calories: editingMeal.calories,
              protein: editingMeal.macronutrients.protein,
              carbs: editingMeal.macronutrients.carbs,
              fats: editingMeal.macronutrients.fats,
            }}
            onSave={handleSave}
            onCancel={() => setEditingMeal(null)}
            saving={updateMeal.isPending}
          />
        )}
      </Modal>
    </div>
  );
}
