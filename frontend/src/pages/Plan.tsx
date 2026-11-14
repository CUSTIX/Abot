import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { api, ApiError } from "../lib/api";
import { isoDate } from "../lib/dates";
import { parseAmount, peso, toDecimalString } from "../lib/money";
import { useLoad, useStore } from "../lib/store";
import type { Bill, Schedule, SplitRule } from "../lib/types";
import { Goals } from "../components/Goals";
import { Sheet } from "../components/Sheet";
import { navigate } from "../lib/router";

const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const ordinal = (n: number) => `${n}${["th", "st", "nd", "rd"][n % 100 > 10 && n % 100 < 14 ? 0 : n % 10] ?? "th"}`;

export function Plan() {
  const [sheet, setSheet] = useState<"pay" | "bill" | "rule" | null>(null);
  const [bill, setBill] = useState<Bill | null>(null);
  const [rule, setRule] = useState<SplitRule | null>(null);
  const bills = useLoad<Bill[]>("bills/");
  const rules = useLoad<SplitRule[]>("split-rules/");
  const { wallets, categories } = useStore();
  const walletName = (id: number | null) => wallets.find((w) => w.id === id)?.name ?? "";
  const catName = (id: number | null) => categories.find((c) => c.id === id)?.name ?? "";

  return (
    <div className="stack">
      <section className="card cta">
        <div>
          <h2 className="card__title">Sahod arrived?</h2>
          <p className="muted small">Record it and split it by your rules in one tap.</p>
        </div>
        <button type="button" className="btn btn--accent" onClick={() => setSheet("pay")}>
          Receive pay
        </button>
      </section>

      <Goals />

      <section className="card cta cta--soft">
        <div>
          <h2 className="card__title">Utang</h2>
          <p className="muted small">Who owes you, and whom you owe. Partial payments too.</p>
        </div>
        <a className="btn" href="/utang" onClick={(e) => (e.preventDefault(), navigate("/utang"))}>
          Open
        </a>
      </section>

      <section className="card cta cta--soft">
        <div>
          <h2 className="card__title">Paluwagan</h2>
          <p className="muted small">Your savings groups: shares due, and when your pot comes.</p>
        </div>
        <a className="btn" href="/paluwagan" onClick={(e) => (e.preventDefault(), navigate("/paluwagan"))}>
          Open
        </a>
      </section>

      <ScheduleCard />

      <section className="card">
        <div className="card__head">
          <h2 className="card__title">Monthly bills</h2>
          <button type="button" className="btn btn--small" onClick={() => (setBill(null), setSheet("bill"))}>
            Add
          </button>
        </div>
        {bills.data?.length ? (
          <ul className="list">
            {bills.data.map((b) => (
              <li key={b.id}>
                <button type="button" className={`row${b.active ? "" : " is-off"}`} onClick={() => (setBill(b), setSheet("bill"))}>
                  <span>
                    <span className="row__title">{b.name}</span>
                    <span className="row__meta">
                      Every {ordinal(b.due_day)} · {walletName(b.wallet)}
                      {b.active ? "" : " · paused"}
                    </span>
                  </span>
                  <span className="row__value">{peso(b.amount)}</span>
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">Rent, Meralco, internet… Bills due before payday are set aside first.</p>
        )}
      </section>

      <section className="card">
        <div className="card__head">
          <h2 className="card__title">Payday split</h2>
          <button type="button" className="btn btn--small" onClick={() => (setRule(null), setSheet("rule"))}>
            Add
          </button>
        </div>
        {rules.data?.length ? (
          <ul className="list">
            {rules.data.map((r) => (
              <li key={r.id}>
                <button type="button" className={`row${r.active ? "" : " is-off"}`} onClick={() => (setRule(r), setSheet("rule"))}>
                  <span>
                    <span className="row__title">{r.name}</span>
                    <span className="row__meta">
                      {r.to_wallet ? `Move to ${walletName(r.to_wallet)}` : `Spend on ${catName(r.category)}`}
                    </span>
                  </span>
                  <span className="row__value">{r.mode === "percent" ? `${Number(r.value)}%` : peso(r.value)}</span>
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">For example: 20% to Savings, ₱3,000 padala to family. Applied when you receive pay.</p>
        )}
      </section>

      <Sheet open={sheet === "pay"} title="Receive pay" onClose={() => setSheet(null)}>
        <ReceivePay onDone={() => setSheet(null)} />
      </Sheet>
      <Sheet open={sheet === "bill"} title={bill ? "Edit bill" : "New bill"} onClose={() => setSheet(null)}>
        <BillForm bill={bill} onDone={() => setSheet(null)} />
      </Sheet>
      <Sheet open={sheet === "rule"} title={rule ? "Edit split rule" : "New split rule"} onClose={() => setSheet(null)}>
        <RuleForm rule={rule} onDone={() => setSheet(null)} />
      </Sheet>
    </div>
  );
}

function useErrors() {
  const [errors, setErrors] = useState<Record<string, string[]>>({});
  const show = (f: string) =>
    errors[f]?.[0] ? (
      <p className="field__error" role="alert">
        {errors[f]?.[0]}
      </p>
    ) : null;
  return { errors, setErrors, show };
}

function ScheduleCard() {
  const { data } = useLoad<Schedule>("schedule/");
  if (!data) return <div className="card skeleton" />;
  return <ScheduleForm key={JSON.stringify(data)} initial={data} />;
}

function ScheduleForm({ initial }: { initial: Schedule }) {
  const { changed, toast } = useStore();
  const [form, setForm] = useState<Schedule>(initial);
  const { setErrors, show } = useErrors();
  const set = <K extends keyof Schedule>(key: K, value: Schedule[K]) => setForm({ ...form, [key]: value });

  async function save(e: FormEvent) {
    e.preventDefault();
    try {
      await api("schedule/", "PUT", form);
      changed();
      toast("Paydays saved");
      setErrors({});
    } catch (err) {
      setErrors(err instanceof ApiError ? err.fields : {});
    }
  }

  const days = Array.from({ length: 31 }, (_, i) => i + 1);
  return (
    <form className="card form" onSubmit={save}>
      <h2 className="card__title">Paydays</h2>
      <label className="field">
        <span>I get paid</span>
        <select value={form.frequency} onChange={(e) => set("frequency", e.target.value as Schedule["frequency"])}>
          <option value="semi_monthly">Twice a month (kinsenas)</option>
          <option value="monthly">Once a month</option>
          <option value="weekly">Every week</option>
        </select>
      </label>
      {form.frequency === "weekly" ? (
        <label className="field">
          <span>On</span>
          <select value={form.weekday} onChange={(e) => set("weekday", Number(e.target.value))}>
            {WEEKDAYS.map((d, i) => (
              <option key={d} value={i}>
                {d}
              </option>
            ))}
          </select>
        </label>
      ) : (
        <div className="field-row">
          <label className="field">
            <span>{form.frequency === "monthly" ? "Day" : "First payday"}</span>
            <select value={form.first_day} onChange={(e) => set("first_day", Number(e.target.value))}>
              {days.map((d) => (
                <option key={d} value={d}>
                  {ordinal(d)}
                </option>
              ))}
            </select>
          </label>
          {form.frequency === "semi_monthly" && (
            <label className="field">
              <span>Second payday</span>
              <select value={form.second_day} onChange={(e) => set("second_day", Number(e.target.value))}>
                {days.map((d) => (
                  <option key={d} value={d}>
                    {d >= 28 ? `${ordinal(d)} (or month end)` : ordinal(d)}
                  </option>
                ))}
              </select>
              {show("second_day")}
            </label>
          )}
        </div>
      )}
      <label className="field">
        <span>If payday is on a weekend</span>
        <select value={form.weekend_rule} onChange={(e) => set("weekend_rule", e.target.value as Schedule["weekend_rule"])}>
          <option value="before">Paid the Friday before</option>
          <option value="after">Paid the Monday after</option>
          <option value="none">Paid on the day itself</option>
        </select>
      </label>
      <label className="field">
        <span>Keep aside (never counted as safe to spend)</span>
        <input inputMode="decimal" value={form.keep_aside} onChange={(e) => set("keep_aside", e.target.value)} />
        {show("keep_aside")}
      </label>
      <button className="btn btn--primary">Save paydays</button>
    </form>
  );
}

function ReceivePay({ onDone }: { onDone: () => void }) {
  const { wallets, categories, changed, toast } = useStore();
  const active = wallets.filter((w) => !w.archived);
  const salary = categories.find((c) => c.kind === "income" && c.name === "Salary");
  const [amount, setAmount] = useState("");
  const [walletId, setWalletId] = useState<number>(
    active.find((w) => w.kind === "bank")?.id ?? active[0]?.id ?? 0,
  );
  const [loaded, setLoaded] = useState<{
    cents: number;
    lines: { name: string; amount: string }[];
    remaining: string;
  } | null>(null);
  const { errors, setErrors, show } = useErrors();
  const [busy, setBusy] = useState(false);
  const cents = parseAmount(amount);
  // Only show a preview that belongs to the amount currently typed.
  const preview = loaded && loaded.cents === cents ? loaded : null;

  useEffect(() => {
    if (cents === null) return;
    let live = true;
    api<{ lines: { name: string; amount: string }[]; remaining: string }>(
      `payday/?amount=${toDecimalString(cents)}`,
    )
      .then((p) => {
        if (!live) return;
        setLoaded({ cents, ...p });
        setErrors({});
      })
      .catch((e) => live && setErrors(e instanceof ApiError ? e.fields : {}));
    return () => {
      live = false;
    };
  }, [cents, setErrors]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (cents === null || busy) return;
    setBusy(true);
    try {
      await api("payday/", "POST", {
        amount: toDecimalString(cents),
        wallet: walletId,
        category: salary?.id ?? null,
        date: isoDate(new Date()),
      });
      changed();
      toast(`Sahod recorded: ${peso(cents)}`);
      onDone();
    } catch (err) {
      setErrors(err instanceof ApiError ? err.fields : {});
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="form" onSubmit={submit} noValidate>
      <label className="field">
        <span>Amount received</span>
        <input className="field__amount" inputMode="decimal" autoFocus placeholder="0.00" value={amount} onChange={(e) => setAmount(e.target.value)} />
        {show("amount")}
      </label>
      <label className="field">
        <span>Into</span>
        <select value={walletId} onChange={(e) => setWalletId(Number(e.target.value))}>
          {active.map((w) => (
            <option key={w.id} value={w.id}>
              {w.name}
            </option>
          ))}
        </select>
      </label>
      {preview && (
        <div className="split-preview">
          <p className="eyebrow">Your split</p>
          <ul>
            {preview.lines.map((l) => (
              <li key={l.name}>
                <span>{l.name}</span>
                <span>−{peso(l.amount)}</span>
              </li>
            ))}
            <li className="split-preview__rest">
              <span>Left to spend</span>
              <span>{peso(preview.remaining)}</span>
            </li>
          </ul>
        </div>
      )}
      {errors.detail && <p className="alert">{errors.detail[0]}</p>}
      <button className="btn btn--primary btn--block" disabled={busy || cents === null || !preview}>
        {busy ? "Saving…" : "Record and split"}
      </button>
    </form>
  );
}

function BillForm({ bill, onDone }: { bill: Bill | null; onDone: () => void }) {
  const { wallets, categories, changed, toast } = useStore();
  const bills = categories.find((c) => c.kind === "expense" && c.name === "Bills");
  const [name, setName] = useState(bill?.name ?? "");
  const [amount, setAmount] = useState(bill?.amount ?? "");
  const [dueDay, setDueDay] = useState(bill?.due_day ?? 15);
  const [walletId, setWalletId] = useState(bill?.wallet ?? wallets.find((w) => w.spendable)?.id ?? 0);
  const [active, setActive] = useState(bill?.active ?? true);
  const { setErrors, show } = useErrors();

  async function submit(e: FormEvent) {
    e.preventDefault();
    const cents = parseAmount(amount);
    if (cents === null) return setErrors({ amount: ["Enter an amount above zero."] });
    const body = {
      name,
      amount: toDecimalString(cents),
      due_day: dueDay,
      wallet: walletId,
      category: bill?.category ?? bills?.id ?? null,
      active,
    };
    try {
      await api(bill ? `bills/${bill.id}/` : "bills/", bill ? "PATCH" : "POST", body);
      changed();
      toast("Bill saved");
      onDone();
    } catch (err) {
      setErrors(err instanceof ApiError ? err.fields : {});
    }
  }

  async function remove() {
    if (!bill || !window.confirm(`Delete ${bill.name}? Past payments stay in your history.`)) return;
    await api(`bills/${bill.id}/`, "DELETE");
    changed();
    onDone();
  }

  return (
    <form className="form" onSubmit={submit} noValidate>
      <label className="field">
        <span>Name</span>
        <input value={name} maxLength={40} placeholder="Meralco" onChange={(e) => setName(e.target.value)} />
        {show("name")}
      </label>
      <div className="field-row">
        <label className="field">
          <span>Amount</span>
          <input inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} />
          {show("amount")}
        </label>
        <label className="field">
          <span>Due every</span>
          <select value={dueDay} onChange={(e) => setDueDay(Number(e.target.value))}>
            {Array.from({ length: 31 }, (_, i) => i + 1).map((d) => (
              <option key={d} value={d}>
                {ordinal(d)}
              </option>
            ))}
          </select>
        </label>
      </div>
      <label className="field">
        <span>Paid from</span>
        <select value={walletId} onChange={(e) => setWalletId(Number(e.target.value))}>
          {wallets.filter((w) => !w.archived).map((w) => (
            <option key={w.id} value={w.id}>
              {w.name}
            </option>
          ))}
        </select>
      </label>
      <label className="check">
        <input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} />
        <span>Active</span>
      </label>
      <div className="form__actions">
        {bill && (
          <button type="button" className="btn btn--ghost btn--danger" onClick={remove}>
            Delete
          </button>
        )}
        <button className="btn btn--primary" disabled={!name.trim()}>
          Save
        </button>
      </div>
    </form>
  );
}

function RuleForm({ rule, onDone }: { rule: SplitRule | null; onDone: () => void }) {
  const { wallets, categories, changed, toast } = useStore();
  const [name, setName] = useState(rule?.name ?? "");
  const [mode, setMode] = useState<SplitRule["mode"]>(rule?.mode ?? "percent");
  const [value, setValue] = useState(rule ? String(Number(rule.value)) : "");
  const [target, setTarget] = useState(rule?.category ? `c${rule.category}` : `w${rule?.to_wallet ?? wallets.find((w) => !w.spendable)?.id ?? ""}`);
  const { setErrors, show } = useErrors();

  async function submit(e: FormEvent) {
    e.preventDefault();
    const amount = mode === "fixed" ? parseAmount(value) : Number(value) > 0 ? Math.round(Number(value) * 100) : null;
    if (amount === null) return setErrors({ value: ["Enter a number above zero."] });
    const id = Number(target.slice(1));
    const body = {
      name,
      mode,
      value: toDecimalString(amount),
      to_wallet: target.startsWith("w") ? id : null,
      category: target.startsWith("c") ? id : null,
    };
    try {
      await api(rule ? `split-rules/${rule.id}/` : "split-rules/", rule ? "PATCH" : "POST", body);
      changed();
      toast("Rule saved");
      onDone();
    } catch (err) {
      setErrors(err instanceof ApiError ? err.fields : {});
    }
  }

  async function remove() {
    if (!rule || !window.confirm(`Delete ${rule.name}?`)) return;
    await api(`split-rules/${rule.id}/`, "DELETE");
    changed();
    onDone();
  }

  return (
    <form className="form" onSubmit={submit} noValidate>
      <label className="field">
        <span>Name</span>
        <input value={name} maxLength={40} placeholder="Ipon" onChange={(e) => setName(e.target.value)} />
        {show("name")}
      </label>
      <div className="segmented" role="radiogroup" aria-label="How much">
        {(["percent", "fixed"] as const).map((m) => (
          <button key={m} type="button" role="radio" aria-checked={mode === m} className={mode === m ? "is-on" : ""} onClick={() => setMode(m)}>
            {m === "percent" ? "Percent of pay" : "Fixed amount"}
          </button>
        ))}
      </div>
      <label className="field">
        <span>{mode === "percent" ? "Percent" : "Amount"}</span>
        <input inputMode="decimal" value={value} onChange={(e) => setValue(e.target.value)} placeholder={mode === "percent" ? "20" : "3000"} />
        {show("value")}
      </label>
      <label className="field">
        <span>Goes to</span>
        <select value={target} onChange={(e) => setTarget(e.target.value)}>
          <optgroup label="Move to a wallet">
            {wallets.filter((w) => !w.archived).map((w) => (
              <option key={w.id} value={`w${w.id}`}>
                {w.name}
              </option>
            ))}
          </optgroup>
          <optgroup label="Spend right away on">
            {categories.filter((c) => c.kind === "expense" && !c.archived).map((c) => (
              <option key={c.id} value={`c${c.id}`}>
                {c.emoji} {c.name}
              </option>
            ))}
          </optgroup>
        </select>
        {show("to_wallet")}
        {show("category")}
      </label>
      <div className="form__actions">
        {rule && (
          <button type="button" className="btn btn--ghost btn--danger" onClick={remove}>
            Delete
          </button>
        )}
        <button className="btn btn--primary" disabled={!name.trim()}>
          Save
        </button>
      </div>
    </form>
  );
}
