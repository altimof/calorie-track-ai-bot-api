/**
 * Format a number with at most two decimal places, without trailing zeros, using the
 * language's decimal separator: 17.599999999999998 -> "17.6" (en) or "17,6" (ru).
 * Intl rounds the decimal value, so 1.005 -> "1.01", unlike Math.round(x * 100) / 100.
 */
export function formatDecimal(value: number, language: string): string {
  return new Intl.NumberFormat(language, { maximumFractionDigits: 2 }).format(
    value,
  );
}
