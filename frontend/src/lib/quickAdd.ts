/* Quick add: turn "kape 150 gcash" into a transaction draft.

   Rules, in order:
   - amount: the first token that reads as money (150, 1,250.50, ₱99, 2.5k)
   - wallets: tokens matching a wallet name (or a common alias: gc -> GCash, paymaya -> Maya)
   - transfer: two wallets, or "to"/"->" between them ("500 gcash to cash")
   - income: a leading "+", or a word that matches an income category ("sahod", "freelance")
   - date: "kahapon"/"yesterday" = yesterday
   - category: a word in a category's keywords or name, else "Other" for expenses
   - everything else is the note
*/
import { addDays } from "./dates";
import { parseAmount, type Centavos } from "./money";
import type { Category, Kind, Wallet } from "./types";

export interface QuickDraft {
  kind: Kind;
  amount: Centavos | null;
  walletId: number | null;
  toWalletId: number | null;
  categoryId: number | null;
  note: string;
  date: string;
  problems: string[];
}

const ALIASES: Record<string, string[]> = {
  gcash: ["gc", "g-cash"],
  maya: ["paymaya", "pm"],
  cash: ["cash", "pera", "wallet"],
  bank: ["bdo", "bpi", "metrobank", "landbank", "unionbank", "security", "atm"],
  savings: ["ipon", "savings"],
};
const YESTERDAY = new Set(["kahapon", "yesterday", "yday"]);
const TRANSFER_WORDS = new Set(["to", "->", "→", "papunta"]);
const IGNORE = new Set(["sa", "from", "via", "using", "with", "ng"]);

const norm = (s: string) => s.toLowerCase().normalize("NFKD").replace(/[^\p{L}\p{N}]+/gu, "");

function matchWallet(token: string, wallets: Wallet[]): Wallet | undefined {
  const t = norm(token);
  if (!t) return undefined;
  return (
    wallets.find((w) => norm(w.name) === t) ??
    wallets.find((w) => (ALIASES[norm(w.name)] ?? []).some((a) => norm(a) === t))
  );
}

function keywordsOf(c: Category): string[] {
  return [c.name, ...c.keywords.split(",")].map((k) => k.trim().toLowerCase()).filter(Boolean);
}

function matchCategory(words: string[], categories: Category[], kind: Kind): Category | undefined {
  const text = ` ${words.join(" ").toLowerCase()} `;
  const pool = categories.filter((c) => !c.archived && (kind === "transfer" || c.kind === kind));
  // Longest keyword wins, so "milk tea" beats "tea".
  let best: { cat: Category; len: number } | undefined;
  for (const cat of pool) {
    for (const k of keywordsOf(cat)) {
      if (text.includes(` ${k} `) && (!best || k.length > best.len)) best = { cat, len: k.length };
    }
  }
  return best?.cat;
}

export function parseQuickAdd(
  text: string,
  wallets: Wallet[],
  categories: Category[],
  today: string,
): QuickDraft {
  const active = wallets.filter((w) => !w.archived);
  const tokens = text.trim().split(/\s+/).filter(Boolean);
  let kind: Kind = "expense";
  let amount: Centavos | null = null;
  let date = today;
  const found: Wallet[] = [];
  let sawTransferWord = false;
  const words: string[] = [];

  if (tokens[0]?.startsWith("+")) {
    kind = "income";
    tokens[0] = tokens[0].slice(1);
    if (!tokens[0]) tokens.shift();
  }

  for (const token of tokens) {
    const lower = token.toLowerCase();
    if (amount === null) {
      const value = parseAmount(token);
      if (value !== null) {
        amount = value;
        continue;
      }
    }
    const wallet = matchWallet(token, active);
    if (wallet && !found.includes(wallet)) {
      found.push(wallet);
      continue;
    }
    if (TRANSFER_WORDS.has(lower) && found.length === 1) {
      sawTransferWord = true;
      continue;
    }
    if (YESTERDAY.has(lower)) {
      date = addDays(today, -1);
      continue;
    }
    if (IGNORE.has(lower)) continue;
    words.push(token);
  }

  if (found.length >= 2 || (sawTransferWord && found.length >= 2)) kind = "transfer";
  if (kind === "expense" && matchCategory(words, categories, "income") && !matchCategory(words, categories, "expense")) {
    kind = "income";
  }

  let categoryId: number | null = null;
  if (kind !== "transfer") {
    const cat =
      matchCategory(words, categories, kind) ??
      categories.find((c) => c.kind === kind && !c.archived && /^other/i.test(c.name));
    categoryId = cat?.id ?? null;
  }

  const fallbackWallet = active.find((w) => w.spendable) ?? active[0];
  const problems: string[] = [];
  if (amount === null) problems.push("Add an amount, like 150.");
  if (!found.length && !fallbackWallet) problems.push("Add a wallet first.");

  return {
    kind,
    amount,
    walletId: (found[0] ?? fallbackWallet)?.id ?? null,
    toWalletId: kind === "transfer" ? (found[1]?.id ?? null) : null,
    categoryId,
    note: words.join(" "),
    date,
    problems,
  };
}
