export function formatDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

/**
 * Parse a "YYYY-MM-DD" calendar date as local midnight. `new Date("YYYY-MM-DD")`
 * means UTC midnight, which shows as the previous day west of UTC.
 */
export function parseLocalDate(value: string): Date {
  const [y, m, d] = value.split("-").map(Number);
  return new Date(y, m - 1, d);
}

/** Every calendar date from `start` (inclusive) to `end` (exclusive), as "YYYY-MM-DD". */
export function eachDate(start: string, end: string): string[] {
  const dates: string[] = [];
  const last = parseLocalDate(end);
  for (
    let d = parseLocalDate(start);
    d < last;
    d = new Date(d.getFullYear(), d.getMonth(), d.getDate() + 1)
  ) {
    dates.push(formatDate(d));
  }
  return dates;
}

/**
 * Date range covering the last `days` days including today, for the
 * statistics API, which treats `end_date` as exclusive.
 */
export function getDateRange(days: number, now: Date = new Date()) {
  const end = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1);
  const start = new Date(
    end.getFullYear(),
    end.getMonth(),
    end.getDate() - days,
  );
  return {
    start_date: formatDate(start),
    end_date: formatDate(end),
  };
}
