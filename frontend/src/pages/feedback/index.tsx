import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useSubmitFeedbackApiV1FeedbackPost } from "@/api/queries/feedback/feedback";
import { useClosingConfirmation } from "@/providers/telegram";

const MAX_LENGTH = 5000;

export default function FeedbackPage() {
  const { t } = useTranslation();
  const [message, setMessage] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const submitFeedback = useSubmitFeedbackApiV1FeedbackPost();
  useClosingConfirmation(message.trim() !== "");

  const handleSubmit = () => {
    if (!message.trim()) return;
    submitFeedback.mutate(
      { data: { message_type: "feedback", message_content: message.trim() } },
      {
        onSuccess: () => {
          setSubmitted(true);
          setMessage("");
        },
      },
    );
  };

  if (submitted) {
    return (
      <div className="flex flex-col items-center gap-4 p-8 text-center">
        <p className="text-lg font-medium text-tg-text">
          {t("feedback.success")}
        </p>
        <button
          type="button"
          onClick={() => setSubmitted(false)}
          className="rounded-lg bg-tg-button px-6 py-2 text-sm font-medium text-tg-button-text"
        >
          {t("feedback.cta")}
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4 p-4">
      <h1 className="text-lg font-semibold text-tg-text">
        {t("feedback.title")}
      </h1>
      <p className="text-sm text-tg-hint">{t("feedback.helpText")}</p>

      <textarea
        value={message}
        onChange={(e) => setMessage(e.target.value)}
        maxLength={MAX_LENGTH}
        rows={6}
        placeholder={t("feedback.messagePlaceholder")}
        className="rounded-xl border border-tg-hint/30 bg-tg-secondary-bg p-3 text-sm text-tg-text placeholder:text-tg-hint"
      />

      <div className="flex items-center justify-between text-xs text-tg-hint">
        <span>
          {MAX_LENGTH - message.length} {t("feedback.charactersRemaining")}
        </span>
      </div>

      {submitFeedback.isError && (
        <p className="text-sm text-red-500">{t("feedback.error")}</p>
      )}

      <button
        type="button"
        onClick={handleSubmit}
        disabled={!message.trim() || submitFeedback.isPending}
        aria-label={t("feedback.submit")}
        className="rounded-lg bg-tg-button py-3 text-sm font-medium text-tg-button-text disabled:opacity-50"
      >
        {submitFeedback.isPending
          ? t("feedback.submitting")
          : t("feedback.submit")}
      </button>
    </div>
  );
}
