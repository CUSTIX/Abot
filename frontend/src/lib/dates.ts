/* Dates are local calendar days as "YYYY-MM-DD" strings (the API's format). */

export function isoDate(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

export function fromIso(iso: string): Date {
  const [y = 1970, m = 1, d = 1] = iso.split("-").map(Number);
  return new Date(y, m - 1, d);
}

export function addDays(iso: string, days: number): string {
  const d = fromIso(iso);
  d.setDate(d.getDate() + days);
  return isoDate(d);
}

const SHORT = new Intl.DateTimeFormat("en-PH", { month: "short", day: "numeric" });
const WEEKDAY = new Intl.DateTimeFormat("en-PH", { weekday: "short", month: "short", day: "numeric" });

export function shortDate(iso: string): string {
  return SHORT.format(fromIso(iso));
}

/** "Today", "Yesterday", or "Wed, Nov 18". */
export function dayLabel(iso: string, today: string): string {
  if (iso === today) return "Today";
  if (iso === addDays(today, -1)) return "Yesterday";
  return WEEKDAY.format(fromIso(iso));
}
