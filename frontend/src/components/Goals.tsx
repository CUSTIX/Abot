import { useState } from "react";
import type { FormEvent } from "react";
import { api, ApiError } from "../lib/api";
import { isoDate, shortDate } from "../lib/dates";
import { parseAmount, peso, toCentavos, toDecimalString } from "../lib/money";
import { useLoad, useStore } from "../lib/store";
import type { Goal } from "../lib/types";
import { Sheet } from "./Sheet";

/* Ipon goals: a target in a savings wallet by a date, and how much to put away each payday. */
export function Goals() {
  const { data } = useLoad<Goal[]>("goals/");
  const [editing, setEditing] = useState<Goal | "new" | null>(null);

  return (
    <section className="card">
      <div className="card__head">
        <h2 className="card__title">Ipon goals</h2>
        <button type="button" className="btn btn--small" onClick={() => setEditing("new")}>
          Add
        </button>
      </div>
      {data?.length ? (
        <ul className="goals">
          {data.map((g) => {
            const pct = Math.min(100, Math.round((toCentavos(g.saved) / toCentavos(g.target)) * 100));
            return (
              <li key={g.id}>
                <button type="button" className={`goal goal--${g.status}`} onClick={() => setEditing(g)}>
                  <span className="goal__top">
                    <span className="goal__name">
                      <span aria-hidden="true">{g.emoji || "🎯"}</span> {g.name}
                    </span>
                    <span className="goal__pct">{pct}%</span>
                  </span>
                  <span className="goal__bar" aria-hidden="true">
                    <span style={{ width: `${pct}%` }} />
                  </span>
                  <span className="goal__meta">
                    {peso(g.saved, { round: true })} of {peso(g.target, { round: true })} in {g.wallet_name} · by {shortDate(g.target_date)}
                  </span>
                  <span className="goal__plan">
                    {g.status === "done"
                      ? "Reached! 🎉"
                      : g.status === "late"
                        ? `Past the date: ${peso(g.missing, { round: true })} to go`
                        : g.paydays_left > 0
                          ? `Save ${peso(g.per_payday, { round: true })} each sahod · ${g.paydays_left} payday${g.paydays_left === 1 ? "" : "s"} left`
                          : `${peso(g.missing, { round: true })} to go before the date`}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="muted">Saving for something? Siargao, a new phone, an emergency fund. Sahod tells you how much to set aside each payday.</p>
      )}
      <Sheet open={editing !== null} title={editing === "new" ? "New goal" : "Edit goal"} onClose={() => setEditing(null)}>
        {editing !== null && <GoalForm goal={editing === "new" ? null : editing} onDone={() => setEditing(null)} />}
      </Sheet>
    </section>
  );
}

function GoalForm({ goal, onDone }: { goal: Goal | null; onDone: () => void }) {
  const { wallets, changed, toast } = useStore();
  const active = wallets.filter((w) => !w.archived);
  const [name, setName] = useState(goal?.name ?? "");
  const [emoji, setEmoji] = useState(goal?.emoji ?? "🎯");
  const [target, setTarget] = useState(goal?.target ?? "");
  const [date, setDate] = useState(goal?.target_date ?? "");
  const [walletId, setWalletId] = useState(goal?.wallet ?? active.find((w) => !w.spendable)?.id ?? active[0]?.id ?? 0);
  const [errors, setErrors] = useState<Record<string, string[]>>({});
  const show = (f: string) => (errors[f]?.[0] ? <p className="field__error">{errors[f]?.[0]}</p> : null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    const cents = parseAmount(target);
    if (cents === null) return setErrors({ target: ["Enter a target above zero."] });
    if (!date) return setErrors({ target_date: ["Pick a date."] });
    const body = { name, emoji, target: toDecimalString(cents), target_date: date, wallet: walletId };
    try {
      await api(goal ? `goals/${goal.id}/` : "goals/", goal ? "PATCH" : "POST", body);
      changed();
      toast("Goal saved");
      onDone();
    } catch (err) {
      setErrors(err instanceof ApiError ? err.fields : {});
    }
  }

  async function remove() {
    if (!goal || !window.confirm(`Delete the goal "${goal.name}"? Your savings stay in ${goal.wallet_name}.`)) return;
    await api(`goals/${goal.id}/`, "DELETE");
    changed();
    onDone();
  }

  return (
    <form className="form" onSubmit={submit} noValidate>
      <div className="field-row field-row--emoji">
        <label className="field">
          <span>Icon</span>
          <input value={emoji} maxLength={4} onChange={(e) => setEmoji(e.target.value)} aria-label="Emoji" />
        </label>
        <label className="field">
          <span>Goal</span>
          <input value={name} maxLength={40} placeholder="Siargao trip" onChange={(e) => setName(e.target.value)} />
          {show("name")}
        </label>
      </div>
      <div className="field-row">
        <label className="field">
          <span>Target</span>
          <input inputMode="decimal" value={target} placeholder="20000" onChange={(e) => setTarget(e.target.value)} />
          {show("target")}
        </label>
        <label className="field">
          <span>By</span>
          <input type="date" value={date} min={isoDate(new Date())} onChange={(e) => setDate(e.target.value)} />
          {show("target_date")}
        </label>
      </div>
      <label className="field">
        <span>Saved in</span>
        <select value={walletId} onChange={(e) => setWalletId(Number(e.target.value))}>
          {active.map((w) => (
            <option key={w.id} value={w.id}>
              {w.name} · {peso(w.balance, { round: true })}
            </option>
          ))}
        </select>
        <small className="muted">Progress is this wallet's balance. A payday split rule to it saves automatically.</small>
      </label>
      <div className="form__actions">
        {goal && (
          <button type="button" className="btn btn--ghost btn--danger" onClick={remove}>
            Delete
          </button>
        )}
        <button className="btn btn--primary" disabled={!name.trim()}>
          Save goal
        </button>
      </div>
    </form>
  );
}
