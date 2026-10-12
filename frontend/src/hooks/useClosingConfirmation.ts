import { useEffect } from "react";

// Number of mounted forms that currently have unsaved changes
let dirtyCount = 0;

/**
 * Ask Telegram to confirm closing the Mini App only while `isDirty` is true.
 * The confirmation is dropped once no form has unsaved changes, including when
 * the form unmounts.
 */
export function useClosingConfirmation(isDirty: boolean): void {
  useEffect(() => {
    if (!isDirty) return;
    const webapp = window.Telegram?.WebApp;

    dirtyCount += 1;
    if (dirtyCount === 1) webapp?.enableClosingConfirmation?.();

    return () => {
      dirtyCount -= 1;
      if (dirtyCount === 0) webapp?.disableClosingConfirmation?.();
    };
  }, [isDirty]);
}
