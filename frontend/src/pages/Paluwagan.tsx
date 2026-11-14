import { useState } from "react";
import type { FormEvent } from "react";
import { api, ApiError } from "../lib/api";
import { dayLabel, isoDate, shortDate } from "../lib/dates";
import { parseAmount, peso, toCentavos, toDecimalString } from "../lib/money";
import { useLoad, useStore } from "../lib/store";
import type { Paluwagan as Group } from "../lib/types";
import { Sheet } from "../components/Sheet";

const FREQ: Record<Group["frequency"], string> = {
  payday: "every payday",
  weekly: "every week",
  monthly: "every month",
};

export function Paluwagan() {
  const { data } = useLoad<Group[]>("paluwagan/");
  const [adding, setAdding] = useState(false);
  const today = isoDate(new Date());

  return (
    <div className="stack">
      <section className="card cta cta--soft">
        <div>
          <h2 className="card__title">Paluwagan</h2>
          <p className="muted small">Pay your share each round; take the whole pot on your turn. Shares are saving, not spending.</p>
        </div>
        <button type="button" className="btn btn--primary" onClick={() => setAdding(true)}>
          New
        </button>
      </section>

      {data && data.length === 0 && <p className="empty">No paluwagan yet.</p>}
      {data?.map((g) => <GroupCard key={g.id} group={g} today={today} />)}

      <Sheet open={adding} title="New paluwagan" onClose={() => setAdding(false)}>
        <NewGroup onDone={() => setAdding(false)} />
      </Sheet>
    </div>
  );
}

function GroupCard({ group, today }: { group: Group; today: string }) {
  const { changed, toast } = useStore();
  const [busy, setBusy] = useState(false);
  const pct = Math.round((toCentavos(group.contributed) / toCentavos(group.total_to_pay)) * 100);
  const myRound = group.rounds[group.my_turn - 1];
  const canCollect = !group.received && myRound !== undefined && myRound.date <= today;

  async function record(kind: "contribution" | "payout", round: number) {
    if (busy) return;
    setBusy(true);
    try {
      await api(`paluwagan/${group.id}/record/`, "POST", { kind, round });
      changed();
      toast(kind === "payout" ? `Pot received: ${peso(group.pot)}` : `Round ${round} share paid`);
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Couldn't save that");
    } finally {
      setBusy(false);
    }
  }

  async function undo(entryId: number, label: string) {
    if (!window.confirm(`Undo ${label}?`)) return;
    await api(`paluwagan/${group.id}/entries/${entryId}/`, "DELETE");
    changed();
  }

  async function remove() {
    if (!window.confirm(`Delete ${group.name}? Its shares and payout are removed from your wallets too.`)) return;
    await api(`paluwagan/${group.id}/`, "DELETE");
    changed();
    toast("Paluwagan deleted");
  }

  return (
    <section className="card group">
      <header className="group__head">
        <div>
          <h2 className="card__title">{group.name}</h2>
          <p className="muted small">
            {peso(group.share)} {FREQ[group.frequency]} · {group.members} members
          </p>
        </div>
        <div className="group__pot">
          <span className="eyebrow">Your pot</span>
          <strong>{peso(group.pot, { round: true })}</strong>
          <span className="small muted">
            {group.received ? "received" : `round ${group.my_turn} · ${shortDate(group.my_turn_date)}`}
          </span>
        </div>
      </header>

      <ol className="rounds" aria-label="Rounds">
        {group.rounds.map((r) => {
          const late = !r.paid && r.date < today;
          const state = r.paid ? "paid" : late ? "late" : "open";
          return (
            <li key={r.round} className={`round round--${state}${r.my_turn ? " round--mine" : ""}`}>
              <button
                type="button"
                className="round__dot"
                disabled={busy}
                title={`Round ${r.round} · ${shortDate(r.date)}${r.my_turn ? " · your turn" : ""}${r.paid ? " · paid" : ""}`}
                aria-label={`Round ${r.round}, ${shortDate(r.date)}${r.my_turn ? ", your turn" : ""}: ${r.paid ? "share paid, tap to undo" : "tap to pay your share"}`}
                onClick={() =>
                  r.paid && r.contribution_id
                    ? undo(r.contribution_id, `round ${r.round}'s share`)
                    : record("contribution", r.round)
                }
              >
                {r.my_turn ? "★" : r.round}
              </button>
              <span className="round__date">{shortDate(r.date)}</span>
            </li>
          );
        })}
      </ol>

      <div className="group__progress">
        <div className="progress" aria-hidden="true">
          <span style={{ width: `${pct}%` }} />
        </div>
        <p className="small muted">
          Paid in {peso(group.contributed)} of {peso(group.total_to_pay)}
          {group.behind > 0 && <span className="danger"> · {group.behind} share{group.behind === 1 ? "" : "s"} behind</span>}
        </p>
      </div>

      <div className="group__actions">
        {group.next_due && (
          <button type="button" className="btn btn--primary" disabled={busy} onClick={() => record("contribution", group.next_due!.round)}>
            Pay round {group.next_due.round} share
            <small> · {dayLabel(group.next_due.date, today)}</small>
          </button>
        )}
        {canCollect && (
          <button type="button" className="btn btn--accent" disabled={busy} onClick={() => record("payout", group.my_turn)}>
            Got my payout
          </button>
        )}
        {group.received && myRound?.payout_id && (
          <button type="button" className="link-btn" onClick={() => undo(myRound.payout_id!, "the payout")}>
            Undo payout
          </button>
        )}
        <button type="button" className="link-btn link-btn--danger" onClick={remove}>
          Delete
        </button>
      </div>
      {group.finished && <p className="alert alert--ok">Done! Every share paid and your pot received.</p>}
    </section>
  );
}

function NewGroup({ onDone }: { onDone: () => void }) {
  const { wallets, changed, toast } = useStore();
  const active = wallets.filter((w) => !w.archived);
  const [name, setName] = useState("");
  const [share, setShare] = useState("");
  const [members, setMembers] = useState(10);
  const [myTurn, setMyTurn] = useState(1);
  const [frequency, setFrequency] = useState<Group["frequency"]>("payday");
  const [start, setStart] = useState(isoDate(new Date()));
  const [walletId, setWalletId] = useState(active.find((w) => w.spendable)?.id ?? 0);
  const [errors, setErrors] = useState<Record<string, string[]>>({});
  const [busy, setBusy] = useState(false);
  const cents = parseAmount(share);
  const show = (f: string) => (errors[f]?.[0] ? <p className="field__error">{errors[f]?.[0]}</p> : null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (cents === null || busy) return setErrors({ share: ["Enter the share per round."] });
    setBusy(true);
    try {
      await api("paluwagan/", "POST", {
        name,
        share: toDecimalString(cents),
        members,
        my_turn: myTurn,
        frequency,
        start_date: start,
        wallet: walletId,
      });
      changed();
      toast("Paluwagan added");
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
        <span>Name</span>
        <input value={name} maxLength={60} autoFocus placeholder="Office paluwagan" onChange={(e) => setName(e.target.value)} />
        {show("name")}
      </label>
      <div className="field-row">
        <label className="field">
          <span>Share per round</span>
          <input inputMode="decimal" value={share} placeholder="1000" onChange={(e) => setShare(e.target.value)} />
          {show("share")}
        </label>
        <label className="field">
          <span>Rounds</span>
          <select value={frequency} onChange={(e) => setFrequency(e.target.value as Group["frequency"])}>
            <option value="payday">Every payday</option>
            <option value="weekly">Weekly</option>
            <option value="monthly">Monthly</option>
          </select>
        </label>
      </div>
      <div className="field-row">
        <label className="field">
          <span>Members</span>
          <select value={members} onChange={(e) => (setMembers(Number(e.target.value)), setMyTurn((t) => Math.min(t, Number(e.target.value))))}>
            {Array.from({ length: 59 }, (_, i) => i + 2).map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
          {show("members")}
        </label>
        <label className="field">
          <span>My turn</span>
          <select value={myTurn} onChange={(e) => setMyTurn(Number(e.target.value))}>
            {Array.from({ length: members }, (_, i) => i + 1).map((n) => (
              <option key={n} value={n}>
                Round {n}
              </option>
            ))}
          </select>
          {show("my_turn")}
        </label>
      </div>
      <div className="field-row">
        <label className="field">
          <span>First round</span>
          <input type="date" value={start} onChange={(e) => setStart(e.target.value)} />
        </label>
        <label className="field">
          <span>Pay from</span>
          <select value={walletId} onChange={(e) => setWalletId(Number(e.target.value))}>
            {active.map((w) => (
              <option key={w.id} value={w.id}>
                {w.name}
              </option>
            ))}
          </select>
        </label>
      </div>
      {cents !== null && (
        <p className="split-preview">
          Your pot: <strong>{peso(cents * members)}</strong> on round {myTurn}.
        </p>
      )}
      {errors.detail && <p className="alert">{errors.detail[0]}</p>}
      <button className="btn btn--primary btn--block" disabled={busy || !name.trim() || cents === null}>
        {busy ? "Saving…" : "Add paluwagan"}
      </button>
    </form>
  );
}
