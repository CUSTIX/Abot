import { useMemo, useState } from "react";
import type { FormEvent } from "react";
import { api, ApiError } from "../lib/api";
import { isoDate } from "../lib/dates";
import { parseAmount, peso, toDecimalString } from "../lib/money";
import { parseQuickAdd } from "../lib/quickAdd";
import { useStore } from "../lib/store";
import type { Kind, Transaction } from "../lib/types";

const KINDS: { value: Kind; label: string }[] = [
  { value: "expense", label: "Expense" },
  { value: "income", label: "Income" },
  { value: "transfer", label: "Transfer" },
];

export function TransactionForm({
  initial,
  onDone,
}: {
  initial?: Transaction;
  onDone: () => void;
}) {
  const { wallets, categories, changed, toast } = useStore();
  const active = wallets.filter((w) => !w.archived);
  const today = isoDate(new Date());

  const [quick, setQuick] = useState("");
  const [kind, setKind] = useState<Kind>(initial?.kind ?? "expense");
  const [amount, setAmount] = useState(initial ? initial.amount : "");
  const [walletId, setWalletId] = useState<number | "">(initial?.wallet ?? active[0]?.id ?? "");
  const [toWalletId, setToWalletId] = useState<number | "">(initial?.to_wallet ?? "");
  const [categoryId, setCategoryId] = useState<number | null>(initial?.category ?? null);
  const [date, setDate] = useState(initial?.date ?? today);
  const [note, setNote] = useState(initial?.note ?? "");
  const [errors, setErrors] = useState<Record<string, string[]>>({});
  const [busy, setBusy] = useState(false);

  const draft = useMemo(
    () => (quick.trim() ? parseQuickAdd(quick, wallets, categories, today) : null),
    [quick, wallets, categories, today],
  );

  function applyQuick(text: string) {
    setQuick(text);
    const d = text.trim() ? parseQuickAdd(text, wallets, categories, today) : null;
    if (!d) return;
    setKind(d.kind);
    if (d.amount !== null) setAmount(toDecimalString(d.amount));
    if (d.walletId) setWalletId(d.walletId);
    setToWalletId(d.toWalletId ?? "");
    setCategoryId(d.categoryId);
    setDate(d.date);
    setNote(d.note);
  }

  const cats = categories.filter((c) => c.kind === kind && !c.archived);
  const cents = parseAmount(amount);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (busy) return;
    if (cents === null) {
      setErrors({ amount: ["Enter an amount above zero."] });
      return;
    }
    setBusy(true);
    const body = {
      kind,
      amount: toDecimalString(cents),
      date,
      wallet: walletId || null,
      to_wallet: kind === "transfer" ? toWalletId || null : null,
      category: kind === "transfer" ? null : categoryId,
      note,
    };
    try {
      if (initial) await api(`transactions/${initial.id}/`, "PATCH", body);
      else await api("transactions/", "POST", body);
      changed();
      toast(initial ? "Saved" : `Added ${peso(cents)}`);
      onDone();
    } catch (err) {
      setErrors(err instanceof ApiError ? err.fields : { detail: [String(err)] });
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!initial || busy || !window.confirm("Delete this transaction?")) return;
    setBusy(true);
    try {
      await api(`transactions/${initial.id}/`, "DELETE");
      changed();
      toast("Deleted");
      onDone();
    } finally {
      setBusy(false);
    }
  }

  const err = (field: string) =>
    errors[field]?.[0] ? (
      <p className="field__error" role="alert">
        {errors[field]?.[0]}
      </p>
    ) : null;

  return (
    <form className="form" onSubmit={submit} noValidate>
      {!initial && (
        <div className="quick">
          <label htmlFor="quick" className="quick__label">
            Quick add
          </label>
          <input
            id="quick"
            className="quick__input"
            placeholder="kape 150 gcash"
            autoComplete="off"
            autoFocus
            value={quick}
            onChange={(e) => applyQuick(e.target.value)}
          />
          <p className="quick__hint">
            {draft && draft.amount !== null
              ? `${draft.kind === "transfer" ? "Transfer" : draft.kind === "income" ? "Income" : "Expense"} · ${peso(draft.amount)}`
              : "Try “jeep 13 cash”, “+25k sahod bank” or “500 gcash to cash”."}
          </p>
        </div>
      )}

      <div className="segmented" role="radiogroup" aria-label="Type">
        {KINDS.map((k) => (
          <button
            key={k.value}
            type="button"
            role="radio"
            aria-checked={kind === k.value}
            className={kind === k.value ? "is-on" : ""}
            onClick={() => {
              setKind(k.value);
              setCategoryId(null);
            }}
          >
            {k.label}
          </button>
        ))}
      </div>

      <label className="field">
        <span>Amount</span>
        <input
          inputMode="decimal"
          className="field__amount"
          placeholder="0.00"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          aria-invalid={Boolean(errors.amount)}
        />
        {err("amount")}
      </label>

      <div className="field-row">
        <label className="field">
          <span>{kind === "transfer" ? "From" : kind === "income" ? "Into" : "From"}</span>
          <select value={walletId} onChange={(e) => setWalletId(Number(e.target.value))}>
            {active.map((w) => (
              <option key={w.id} value={w.id}>
                {w.name} · {peso(w.balance, { round: true })}
              </option>
            ))}
          </select>
          {err("wallet")}
        </label>
        {kind === "transfer" ? (
          <label className="field">
            <span>To</span>
            <select value={toWalletId} onChange={(e) => setToWalletId(Number(e.target.value) || "")}>
              <option value="">Pick a wallet</option>
              {active
                .filter((w) => w.id !== walletId)
                .map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.name}
                  </option>
                ))}
            </select>
            {err("to_wallet")}
          </label>
        ) : (
          <label className="field">
            <span>Date</span>
            <input type="date" value={date} max={today} onChange={(e) => setDate(e.target.value)} />
            {err("date")}
          </label>
        )}
      </div>

      {kind !== "transfer" && (
        <fieldset className="field">
          <legend>Category</legend>
          <div className="chips">
            {cats.map((c) => (
              <button
                key={c.id}
                type="button"
                className={`chip${categoryId === c.id ? " is-on" : ""}`}
                aria-pressed={categoryId === c.id}
                onClick={() => setCategoryId(categoryId === c.id ? null : c.id)}
              >
                <span aria-hidden="true">{c.emoji}</span> {c.name}
              </button>
            ))}
          </div>
          {err("category")}
        </fieldset>
      )}

      <label className="field">
        <span>Note</span>
        <input value={note} maxLength={120} onChange={(e) => setNote(e.target.value)} />
      </label>

      {(errors.detail || errors.non_field_errors) && (
        <p className="alert" role="alert">
          {errors.detail?.[0] ?? errors.non_field_errors?.[0]}
        </p>
      )}

      <div className="form__actions">
        {initial && (
          <button type="button" className="btn btn--ghost btn--danger" onClick={remove} disabled={busy}>
            Delete
          </button>
        )}
        <button type="submit" className="btn btn--primary" disabled={busy || cents === null}>
          {busy ? "Saving…" : initial ? "Save" : cents !== null ? `Add ${peso(cents)}` : "Add"}
        </button>
      </div>
    </form>
  );
}
