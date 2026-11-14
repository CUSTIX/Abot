/* Money in the app is always integer centavos (never float arithmetic). The API sends and
   receives decimal strings like "1250.50"; convert at the edges. */

export type Centavos = number;

const PESO = new Intl.NumberFormat("en-PH", {
  style: "currency",
  currency: "PHP",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});
const PESO_ROUND = new Intl.NumberFormat("en-PH", {
  style: "currency",
  currency: "PHP",
  maximumFractionDigits: 0,
});

/** "1250.50" -> 125050. Throws on anything that isn't a plain decimal amount. */
export function toCentavos(value: string): Centavos {
  const match = /^(-)?(\d+)(?:\.(\d{1,2}))?$/.exec(value.trim());
  if (!match) throw new Error(`Not an amount: ${value}`);
  const [, minus, whole = "0", frac = ""] = match;
  const cents = Number(whole) * 100 + Number(frac.padEnd(2, "0"));
  return minus ? -cents : cents;
}

/** 125050 -> "1250.50" (what the API expects). */
export function toDecimalString(cents: Centavos): string {
  const sign = cents < 0 ? "-" : "";
  const abs = Math.abs(Math.trunc(cents));
  return `${sign}${Math.floor(abs / 100)}.${String(abs % 100).padStart(2, "0")}`;
}

/** Display: "₱1,250.50". Pass `round` for big headline numbers ("₱1,251"). */
export function peso(value: string | Centavos, opts: { round?: boolean } = {}): string {
  const cents = typeof value === "number" ? value : toCentavos(value);
  return (opts.round ? PESO_ROUND : PESO).format(cents / 100);
}

/** Parse what people type: "150", "1,250.5", "₱99", "1.5k", "2k". Returns null if unclear. */
export function parseAmount(text: string): Centavos | null {
  const cleaned = text.trim().toLowerCase().replace(/^₱|^php|^p(?=\d)/, "").replace(/,/g, "");
  const match = /^(\d+(?:\.\d{1,2})?)(k)?$/.exec(cleaned);
  if (!match) return null;
  const [, num = "0", k] = match;
  if (k) {
    const [whole = "0", frac = ""] = num.split(".");
    // 1.5k = 1500.00, done on strings so no float error creeps in
    const thousandths = Number(whole) * 1000 + Number(frac.padEnd(3, "0").slice(0, 3));
    return thousandths * 100;
  }
  const cents = toCentavos(num);
  return cents > 0 ? cents : null;
}
