import { useState } from "react";
import type { FormEvent } from "react";
import { api, ApiError } from "../lib/api";
import { dayLabel, isoDate, shortDate } from "../lib/dates";
import { parseAmount, peso, toCentavos, toDecimalString } from "../lib/money";
import { useLoad, useStore } from "../lib/store";
import type { Utang as UtangRow } from "../lib/types";
import { Sheet } from "../components/Sheet";

type Tab = "open" | "settled";

export function Utang() {
  const { data } = useLoad<UtangRow[]>("utang/");
  const [tab, setTab] = useState<Tab>("open");
  const [adding, setAdding] = useState(false);
  const [openId, setOpenId] = useState<number | null>(null);
  const today = isoDate(new Date());
  const rows = data ?? [];
  const isOpen = (u: UtangRow) => toCentavos(u.remaining) > 0;
  const owedToMe = rows.filter((u) => u.direction === "lent").reduce((s, u) => s + toCentavos(u.remaining), 0);
  const iOwe = rows.filter((u) => u.direction === "borrowed").reduce((s, u) => s + toCentavos(u.remaining), 0);
  const shown = rows
    .filter((u) => (tab === "open" ? isOpen(u) : !isOpen(u)))
    .sort((a, b) => (a.due_date ?? "9999").localeCompare(b.due_date ?? "9999"));
  const selected = rows.find((u) => u.id === openId) ?? null;

  return (
    <div className="stack">
      <section className="card utang-totals">
        <div>
          <p className="eyebrow">Owed to you</p>
          <p className="utang-totals__in">{peso(owedToMe)}</p>
        </div>
        <div>
          <p className="eyebrow">You owe</p>
          <p className="utang-totals__out">{peso(iOwe)}</p>
        </div>
      </section>

      <div className="toolbar toolbar--row">
        <div className="segmented" role="radiogroup" aria-label="Show">
          {(["open", "settled"] as const).map((t) => (
            <button key={t} type="button" role="radio" aria-checked={tab === t} className={tab === t ? "is-on" : ""} onClick={() => setTab(t)}>
              {t === "open" ? "Open" : "Settled"}
            </button>
          ))}
        </div>
        <button type="button" className="btn btn--primary" onClick={() => setAdding(true)}>
          New utang
        </button>
      </div>

      {data && shown.length === 0 && (
        <p className="empty">
          {tab === "open" ? "No open utang. Lending or borrowing? Add it so you don't forget." : "Nothing settled yet."}
        </p>
      )}

      <ul className="utang-list">
        {shown.map((u) => {
          const total = toCentavos(u.amount);
          const paidPct = Math.round((toCentavos(u.paid) / total) * 100);
          const overdue = isOpen(u) && u.due_date !== null && u.due_date < today;
          return (
            <li key={u.id}>
              <button type="button" className={`utang utang--${u.direction}`} onClick={() => setOpenId(u.id)}>
                <span className="utang__avatar" aria-hidden="true">
                  {u.person.trim().charAt(0).toUpperCase()}
                </span>
                <span className="utang__body">
                  <span className="utang__person">{u.person}</span>
                  <span className={`utang__meta${overdue ? " danger" : ""}`}>
                    {u.direction === "lent" ? "Owes you" : "You owe"}
                    {u.due_date && isOpen(u) ? ` · ${overdue ? "overdue since" : "due"} ${shortDate(u.due_date)}` : ""}
                    {!isOpen(u) ? " · settled" : ""}
                  </span>
                  <span className="utang__bar" aria-hidden="true">
                    <span style={{ width: `${paidPct}%` }} />
                  </span>
                </span>
                <span className="utang__amount">
                  {peso(isOpen(u) ? u.remaining : u.amount)}
                  {isOpen(u) && toCentavos(u.paid) > 0 && <small>of {peso(u.amount, { round: true })}</small>}
                </span>
              </button>
            </li>
          );
        })}
      </ul>

      <Sheet open={adding} title="New utang" onClose={() => setAdding(false)}>
        <NewUtang onDone={() => setAdding(false)} />
      </Sheet>
      <Sheet open={selected !== null} title={selected?.person ?? ""} onClose={() => setOpenId(null)}>
        {selected && <UtangDetail key={selected.id} utang={selected} onClose={() => setOpenId(null)} today={today} />}
      </Sheet>
    </div>
  );
}

function useFieldErrors() {
  const [errors, setErrors] = useState<Record<string, string[]>>({});
  const show = (f: string) =>
    errors[f]?.[0] ? (
      <p className="field__error" role="alert">
        {errors[f]?.[0]}
      </p>
    ) : null;
  return { errors, setErrors, show };
}

function NewUtang({ onDone }: { onDone: () => void }) {
  const { wallets, changed, toast } = useStore();
  const active = wallets.filter((w) => !w.archived);
  const today = isoDate(new Date());
  const [direction, setDirection] = useState<"lent" | "borrowed">("lent");
  const [person, setPerson] = useState("");
  const [amount, setAmount] = useState("");
  const [date, setDate] = useState(today);
  const [due, setDue] = useState("");
  const [walletId, setWalletId] = useState<string>(String(active.find((w) => w.spendable)?.id ?? ""));
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const { errors, setErrors, show } = useFieldErrors();
  const cents = parseAmount(amount);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (busy) return;
    if (cents === null) return setErrors({ amount: ["Enter an amount above zero."] });
    setBusy(true);
    try {
      await api("utang/", "POST", {
        direction,
        person,
        amount: toDecimalString(cents),
        date,
        due_date: due || null,
        wallet: walletId ? Number(walletId) : null,
        note,
      });
      changed();
      toast(direction === "lent" ? `${person} owes you ${peso(cents)}` : `You owe ${person} ${peso(cents)}`);
      onDone();
    } catch (err) {
      setErrors(err instanceof ApiError ? err.fields : {});
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="form" onSubmit={submit} noValidate>
      <div className="segmented" role="radiogroup" aria-label="Direction">
        {(["lent", "borrowed"] as const).map((d) => (
          <button key={d} type="button" role="radio" aria-checked={direction === d} className={direction === d ? "is-on" : ""} onClick={() => setDirection(d)}>
            {d === "lent" ? "I lent money" : "I borrowed"}
          </button>
        ))}
      </div>
      <label className="field">
        <span>{direction === "lent" ? "Who owes you?" : "Who did you borrow from?"}</span>
        <input value={person} maxLength={60} autoFocus placeholder="Pedro" onChange={(e) => setPerson(e.target.value)} />
        {show("person")}
      </label>
      <label className="field">
        <span>Amount</span>
        <input className="field__amount" inputMode="decimal" placeholder="0.00" value={amount} onChange={(e) => setAmount(e.target.value)} />
        {show("amount")}
      </label>
      <div className="field-row">
        <label className="field">
          <span>Date</span>
          <input type="date" value={date} max={today} onChange={(e) => setDate(e.target.value)} />
        </label>
        <label className="field">
          <span>Due (optional)</span>
          <input type="date" value={due} min={date} onChange={(e) => setDue(e.target.value)} />
          {show("due_date")}
        </label>
      </div>
      <label className="field">
        <span>{direction === "lent" ? "Money came out of" : "Money went into"}</span>
        <select value={walletId} onChange={(e) => setWalletId(e.target.value)}>
          {active.map((w) => (
            <option key={w.id} value={w.id}>
              {w.name}
            </option>
          ))}
          <option value="">Don't touch my wallets (old utang)</option>
        </select>
        <small className="muted">Moves your balance, but never counts as spending or income.</small>
      </label>
      <label className="field">
        <span>Note</span>
        <input value={note} maxLength={120} placeholder="for tuition" onChange={(e) => setNote(e.target.value)} />
      </label>
      {errors.detail && <p className="alert">{errors.detail[0]}</p>}
      <button className="btn btn--primary btn--block" disabled={busy || !person.trim() || cents === null}>
        {busy ? "Saving…" : "Save utang"}
      </button>
    </form>
  );
}

function UtangDetail({ utang, onClose, today }: { utang: UtangRow; onClose: () => void; today: string }) {
  const { wallets, changed, toast } = useStore();
  const active = wallets.filter((w) => !w.archived);
  const remaining = toCentavos(utang.remaining);
  const [amount, setAmount] = useState(remaining > 0 ? toDecimalString(remaining) : "");
  const [walletId, setWalletId] = useState<string>(String(active.find((w) => w.spendable)?.id ?? ""));
  const [busy, setBusy] = useState(false);
  const { setErrors, show } = useFieldErrors();
  const lent = utang.direction === "lent";

  async function pay(e: FormEvent) {
    e.preventDefault();
    const cents = parseAmount(amount);
    if (cents === null || busy) return setErrors({ amount: ["Enter an amount above zero."] });
    setBusy(true);
    try {
      await api(`utang/${utang.id}/pay/`, "POST", {
        amount: toDecimalString(cents),
        date: today,
        wallet: walletId ? Number(walletId) : null,
      });
      changed();
      toast(cents === remaining ? "Settled. Salamat!" : `Payment of ${peso(cents)} recorded`);
      setErrors({});
      setAmount("");
    } catch (err) {
      setErrors(err instanceof ApiError ? err.fields : {});
    } finally {
      setBusy(false);
    }
  }

  async function removePayment(id: number) {
    if (!window.confirm("Remove this payment?")) return;
    await api(`utang/${utang.id}/payments/${id}/`, "DELETE");
    changed();
  }

  async function remove() {
    if (!window.confirm(`Delete this utang with ${utang.person}? Its money moves are undone too.`)) return;
    await api(`utang/${utang.id}/`, "DELETE");
    changed();
    toast("Utang deleted");
    onClose();
  }

  return (
    <div className="stack">
      <div className="utang-head">
        <p className="eyebrow">{lent ? `${utang.person} owes you` : `You owe ${utang.person}`}</p>
        <p className="utang-head__amount">{peso(utang.remaining)}</p>
        <p className="muted small">
          {peso(utang.amount)} on {shortDate(utang.date)}
          {utang.due_date ? ` · due ${dayLabel(utang.due_date, today)}` : ""}
          {utang.note ? ` · ${utang.note}` : ""}
        </p>
      </div>

      {remaining > 0 && (
        <form className="form card" onSubmit={pay} noValidate>
          <h3 className="card__title">{lent ? "They paid back" : "I paid back"}</h3>
          <div className="field-row">
            <label className="field">
              <span>Amount</span>
              <input inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} />
              {show("amount")}
            </label>
            <label className="field">
              <span>{lent ? "Into" : "From"}</span>
              <select value={walletId} onChange={(e) => setWalletId(e.target.value)}>
                {active.map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.name}
                  </option>
                ))}
                <option value="">No wallet</option>
              </select>
            </label>
          </div>
          <button className="btn btn--primary" disabled={busy}>
            {busy ? "Saving…" : "Record payment"}
          </button>
        </form>
      )}

      {utang.payments.length > 0 && (
        <section>
          <h3 className="card__title">Payments</h3>
          <ul className="list">
            {utang.payments.map((p) => (
              <li key={p.id} className="payment">
                <span>{dayLabel(p.date, today)}</span>
                <span className="payment__amount">{peso(p.amount)}</span>
                <button type="button" className="link-btn link-btn--danger" onClick={() => removePayment(p.id)} aria-label={`Remove payment of ${peso(p.amount)}`}>
                  Remove
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      <button type="button" className="btn btn--ghost btn--danger" onClick={remove}>
        Delete utang
      </button>
    </div>
  );
}
