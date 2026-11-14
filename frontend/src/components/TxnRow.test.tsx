import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Transaction } from "../lib/types";
import { TxnRow } from "./TxnRow";

afterEach(cleanup);

const base: Transaction = {
  id: 1,
  kind: "expense",
  amount: "150.00",
  date: "2026-11-20",
  wallet: 2,
  to_wallet: null,
  category: 10,
  note: "kape",
  neutral: false,
  source: "",
  wallet_name: "GCash",
  to_wallet_name: null,
  category_name: "Food & drinks",
  category_emoji: "🍜",
};

const row = (txn: Partial<Transaction>, onClick = () => undefined) =>
  render(
    <ul>
      <TxnRow txn={{ ...base, ...txn }} today="2026-11-20" onClick={onClick} />
    </ul>,
  );

describe("TxnRow", () => {
  it("shows an expense with its category, wallet and day", () => {
    row({});
    expect(screen.getByText("kape")).toBeTruthy();
    expect(screen.getByText("Food & drinks · GCash · Today")).toBeTruthy();
    expect(screen.getByText(/−\s*₱150\.00/)).toBeTruthy();
  });

  it("shows transfers as from → to without a sign", () => {
    row({ kind: "transfer", to_wallet: 1, to_wallet_name: "Cash", category: null, category_name: null });
    expect(screen.getByText("GCash → Cash")).toBeTruthy();
    expect(screen.getByText("₱150.00")).toBeTruthy();
  });

  it("labels utang moves and never shows them as plain spending", () => {
    row({ neutral: true, source: "utang", note: "Lent to Pedro", category: null, category_name: null });
    expect(screen.getByText("Utang · GCash · Today")).toBeTruthy();
    expect(document.querySelector(".txn__amount--neutral")).toBeTruthy();
  });

  it("renders text from the server as text, never as HTML", () => {
    row({ note: "<img src=x onerror=alert(1)>" });
    expect(screen.getByText("<img src=x onerror=alert(1)>")).toBeTruthy();
    expect(document.querySelector("img")).toBeNull();
  });

  it("opens on click", async () => {
    const onClick = vi.fn();
    row({}, onClick);
    await userEvent.click(screen.getByRole("button"));
    expect(onClick).toHaveBeenCalledOnce();
  });
});
