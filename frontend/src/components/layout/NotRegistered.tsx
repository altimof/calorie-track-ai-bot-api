import { useTranslation } from "react-i18next";

export function NotRegistered() {
  const { t } = useTranslation();
  const webapp = window.Telegram?.WebApp;

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-tg-bg p-6 text-center text-tg-text">
      <h1 className="text-xl font-semibold">{t("notRegistered.title")}</h1>
      <p className="text-sm text-tg-hint">{t("notRegistered.message")}</p>
      {webapp?.initData && (
        <button
          onClick={() => webapp.close()}
          className="rounded-lg bg-tg-button px-6 py-2 text-sm font-medium text-tg-button-text"
        >
          {t("notRegistered.close")}
        </button>
      )}
    </div>
  );
}
