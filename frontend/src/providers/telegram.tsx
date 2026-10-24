import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  useMemo,
  useRef,
  type ReactNode,
} from "react";
import i18n from "@/i18n";

interface SafeAreaInsets {
  top: number;
  bottom: number;
  left: number;
  right: number;
}

interface TelegramContextValue {
  user: TelegramWebAppUser | null;
  initData: string | null;
  theme: "light" | "dark";
  language: "en" | "ru";
  safeAreas: SafeAreaInsets;
  setTheme: (theme: "light" | "dark") => void;
  setLanguage: (lang: "en" | "ru") => void;
}

const TelegramContext = createContext<TelegramContextValue | null>(null);

// Marks a form as having unsaved changes (or not). Each form passes its own token.
type SetFormDirty = (form: symbol, dirty: boolean) => void;
const ClosingConfirmationContext = createContext<SetFormDirty | null>(null);

function resolveTheme(): "light" | "dark" {
  const tgScheme = window.Telegram?.WebApp?.colorScheme;
  if (tgScheme === "light" || tgScheme === "dark") return tgScheme;
  if (window.matchMedia?.("(prefers-color-scheme: dark)").matches)
    return "dark";
  return "light";
}

function resolveLanguage(): "en" | "ru" {
  const tgLang = window.Telegram?.WebApp?.initDataUnsafe?.user?.language_code;
  if (tgLang === "ru") return "ru";
  if (typeof navigator !== "undefined" && navigator.language?.startsWith("ru"))
    return "ru";
  return "en";
}

function getSafeAreas(): SafeAreaInsets {
  if (typeof document === "undefined")
    return { top: 0, bottom: 0, left: 0, right: 0 };
  const style = getComputedStyle(document.documentElement);
  return {
    top: parseFloat(style.getPropertyValue("--safe-area-top")) || 0,
    bottom: parseFloat(style.getPropertyValue("--safe-area-bottom")) || 0,
    left: parseFloat(style.getPropertyValue("--safe-area-left")) || 0,
    right: parseFloat(style.getPropertyValue("--safe-area-right")) || 0,
  };
}

export function TelegramProvider({ children }: { children: ReactNode }) {
  const webapp = window.Telegram?.WebApp;
  const user = webapp?.initDataUnsafe?.user ?? null;
  const initData = webapp?.initData ?? null;

  const [theme, setThemeState] = useState<"light" | "dark">(resolveTheme);
  const [language, setLanguageState] = useState<"en" | "ru">(resolveLanguage);
  const [safeAreas, setSafeAreas] = useState<SafeAreaInsets>(getSafeAreas);

  const setTheme = useCallback((t: "light" | "dark") => {
    setThemeState(t);
    document.documentElement.setAttribute("data-theme", t);
  }, []);

  const setLanguage = useCallback((lang: "en" | "ru") => {
    setLanguageState(lang);
    i18n.changeLanguage(lang);
  }, []);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  useEffect(() => {
    i18n.changeLanguage(language);
  }, [language]);

  // Forms with unsaved changes. Telegram asks to confirm closing the Mini App
  // only while this is non-empty; adding or removing a form twice has no effect.
  const dirtyForms = useRef(new Set<symbol>());
  const setFormDirty = useCallback<SetFormDirty>((form, dirty) => {
    const forms = dirtyForms.current;
    const wasDirty = forms.size > 0;
    if (dirty) forms.add(form);
    else forms.delete(form);
    const tg = window.Telegram?.WebApp;
    if (!wasDirty && forms.size > 0) tg?.enableClosingConfirmation?.();
    if (wasDirty && forms.size === 0) tg?.disableClosingConfirmation?.();
  }, []);

  useEffect(() => {
    const handleResize = () => setSafeAreas(getSafeAreas());
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  const value = useMemo(
    () => ({
      user,
      initData,
      theme,
      language,
      safeAreas,
      setTheme,
      setLanguage,
    }),
    [user, initData, theme, language, safeAreas, setTheme, setLanguage],
  );

  return (
    <TelegramContext.Provider value={value}>
      <ClosingConfirmationContext.Provider value={setFormDirty}>
        {children}
      </ClosingConfirmationContext.Provider>
    </TelegramContext.Provider>
  );
}

export function useTelegram(): TelegramContextValue {
  const context = useContext(TelegramContext);
  if (!context)
    throw new Error("useTelegram must be used within TelegramProvider");
  return context;
}

/**
 * Ask Telegram to confirm closing the Mini App while `isDirty` is true, i.e. while
 * this form has unsaved changes. The form stops counting when it is saved,
 * cancelled or unmounted. Does nothing outside TelegramProvider.
 */
export function useClosingConfirmation(isDirty: boolean): void {
  const setFormDirty = useContext(ClosingConfirmationContext);
  const [form] = useState(() => Symbol("form"));

  useEffect(() => {
    if (!setFormDirty || !isDirty) return;
    setFormDirty(form, true);
    return () => setFormDirty(form, false);
  }, [setFormDirty, form, isDirty]);
}
