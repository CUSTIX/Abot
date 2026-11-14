import { describe, expect, it } from "vitest";
import { parseQuickAdd } from "./quickAdd";
import type { Category, Wallet } from "./types";

const wallet = (id: number, name: string, kind: Wallet["kind"] = "ewallet", spendable = true): Wallet => ({
  id,
  name,
  kind,
  opening_balance: "0",
  spendable,
  color: "#000000",
  archived: false,
  sort_order: id,
  balance: "0",
});
const category = (id: number, name: string, kind: Category["kind"], keywords = ""): Category => ({
  id,
  name,
  kind,
  emoji: "",
  keywords,
  archived: false,
});

const WALLETS = [wallet(1, "Cash", "cash"), wallet(2, "GCash"), wallet(3, "Maya"), wallet(4, "Bank", "bank"), wallet(5, "Savings", "savings", false)];
const CATS = [
  category(10, "Food & drinks", "expense", "kape, coffee, lunch, milk tea, tea"),
  category(11, "Transport", "expense", "jeep, grab, mrt"),
  category(12, "Other", "expense"),
  category(13, "Drinks", "expense", "tea"),
  category(20, "Salary", "income", "sahod, salary"),
  category(21, "Other income", "income"),
];
const TODAY = "2026-11-20";
const parse = (text: string) => parseQuickAdd(text, WALLETS, CATS, TODAY);

describe("quick add", () => {
  it("reads 'kape 150 gcash' as a GCash food expense", () => {
    expect(parse("kape 150 gcash")).toMatchObject({
      kind: "expense",
      amount: 15000,
      walletId: 2,
      categoryId: 10,
      note: "kape",
      date: TODAY,
      problems: [],
    });
  });

  it("works in any order and with aliases", () => {
    expect(parse("gc 99.50 grab")).toMatchObject({ amount: 9950, walletId: 2, categoryId: 11 });
    expect(parse("150 paymaya lunch")).toMatchObject({ walletId: 3, categoryId: 10 });
    expect(parse("bdo 2k grab")).toMatchObject({ walletId: 4, amount: 200000 });
  });

  it("detects income from '+' or an income keyword", () => {
    expect(parse("+25k bank")).toMatchObject({ kind: "income", amount: 2500000, walletId: 4, categoryId: 21 });
    expect(parse("sahod 25000 bank")).toMatchObject({ kind: "income", categoryId: 20 });
  });

  it("detects transfers between two wallets", () => {
    expect(parse("500 gcash to cash")).toMatchObject({
      kind: "transfer",
      amount: 50000,
      walletId: 2,
      toWalletId: 1,
      categoryId: null,
    });
    expect(parse("bank savings 3000")).toMatchObject({ kind: "transfer", walletId: 4, toWalletId: 5 });
  });

  it("understands kahapon / yesterday", () => {
    expect(parse("jeep 13 kahapon").date).toBe("2026-11-19");
    expect(parse("yesterday grab 230").date).toBe("2026-11-19");
  });

  it("prefers the longest keyword ('milk tea' over 'tea')", () => {
    expect(parse("milk tea 120").categoryId).toBe(10);
  });

  it("falls back to Other and the first spendable wallet", () => {
    expect(parse("tsinelas 250")).toMatchObject({ categoryId: 12, walletId: 1, note: "tsinelas" });
  });

  it("asks for an amount when there is none", () => {
    expect(parse("kape gcash").problems).toContain("Add an amount, like 150.");
    expect(parse("kape gcash").amount).toBeNull();
  });

  it("only uses the first number as the amount", () => {
    expect(parse("7eleven 85 2pcs")).toMatchObject({ amount: 8500 });
  });

  it("ignores archived wallets", () => {
    const archived = WALLETS.map((w) => (w.name === "Maya" ? { ...w, archived: true } : w));
    expect(parseQuickAdd("150 maya", archived, CATS, TODAY).walletId).toBe(1);
  });
});
