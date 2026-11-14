import { useState } from "react";
import { api, ApiError } from "../lib/api";
import { dayLabel, fromIso, shortDate } from "../lib/dates";
import { peso, toCentavos } from "../lib/money";
import { navigate } from "../lib/router";
import { useLoad, useStore } from "../lib/store";
import type { Today as TodayData, Transaction } from "../lib/types";
import { TxnRow } from "../components/TxnRow";

const STATUS_TEXT: Record<TodayData["status"], string> = {
  ok: "You're on track.",
  tight: "Easy for the rest of today.",
  over: "Over today's budget. Tomorrow's share gets a little smaller.",
  short: "Bills take everything until payday. Hold off on extras.",
};

export function Today({ onEdit }: { onEdit: (t: Transaction) => void }) {
  const { data, error } = useLoad<TodayData>("today/");
  const { changed, toast } = useStore();
  const [paying, setPaying] = useState<string | null>(null);

  if (error && !data) return <p className="alert">{error}</p>;
  if (!data) return <div className="skeleton" aria-busy="true" aria-label="Loading" />;

  const perDay = toCentavos(data.per_day);
  const left = toCentavos(data.left_today);
  const spent = toCentavos(data.spent_today);
  const usedPct = perDay > 0 ? Math.min(100, Math.round((spent / perDay) * 100)) : 100;
  const cycleDays = Math.max(
    1,
    Math.round((fromIso(data.next_payday).getTime() - fromIso(data.cycle_start).getTime()) / 864e5),
  );
  const cyclePct = Math.round(((cycleDays - data.days_left) / cycleDays) * 100);
  const maxSpend = Math.max(1, ...data.cycle_spending.map((c) => toCentavos(c.total)));

  async function pay(billId: number, due: string) {
    const key = `${billId}-${due}`;
    if (paying) return;
    setPaying(key);
    try {
      await api(`bills/${billId}/pay/`, "POST", { due_date: due });
      changed();
      toast("Bill paid");
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Couldn't mark it paid");
    } finally {
      setPaying(null);
    }
  }

  return (
    <div className="stack">
      <section className={`hero hero--${data.status}`} aria-labelledby="safe-label">
        <p id="safe-label" className="hero__label">
          Safe to spend today
        </p>
        <p className="hero__amount" aria-live="polite">
          {peso(Math.max(left, 0), { round: left >= 100000 })}
        </p>
        <div
          className="meter"
          role="meter"
          aria-label="Today's budget used"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={usedPct}
        >
          <span style={{ width: `${usedPct}%` }} />
        </div>
        <p className="hero__sub">
          {spent > 0 ? `${peso(spent)} spent of ${peso(perDay)} today` : `${peso(perDay)} a day until sahod`}
        </p>
        <p className="hero__status">{left < 0 ? `${peso(-left)} over. ` : ""}{STATUS_TEXT[data.status]}</p>
      </section>

      <section className="card payday">
        <div className="payday__row">
          <div>
            <p className="eyebrow">Next sahod</p>
            <p className="payday__date">{dayLabel(data.next_payday, data.today)}</p>
          </div>
          <p className="payday__count">
            <strong>{data.days_left}</strong> day{data.days_left === 1 ? "" : "s"}
          </p>
        </div>
        <div className="progress" aria-hidden="true">
          <span style={{ width: `${cyclePct}%` }} />
        </div>
        <dl className="breakdown">
          <div>
            <dt>Spendable now</dt>
            <dd>{peso(data.spendable)}</dd>
          </div>
          <div>
            <dt>Bills still due</dt>
            <dd>−{peso(data.bills_reserved)}</dd>
          </div>
          {toCentavos(data.keep_aside) > 0 && (
            <div>
              <dt>Buffer</dt>
              <dd>−{peso(data.keep_aside)}</dd>
            </div>
          )}
          <div className="breakdown__total">
            <dt>Free until payday</dt>
            <dd>{peso(data.free_until_payday)}</dd>
          </div>
        </dl>
        {!data.has_schedule && (
          <button type="button" className="btn btn--ghost btn--small" onClick={() => navigate("/plan")}>
            Set your paydays (now assuming the 15th and 30th)
          </button>
        )}
      </section>

      <section className="card">
        <h2 className="card__title">Due before payday</h2>
        {data.commitments.length > 0 && (
          <ul className="list commitments">
            {data.commitments.map((c) => (
              <li key={`${c.kind}-${c.id}`} className="bill">
                <div>
                  <p className="bill__name">{c.label}</p>
                  <p className={`small ${c.overdue ? "danger" : "muted"}`}>
                    {c.overdue ? `Overdue since ${shortDate(c.due_date)}` : `Due ${dayLabel(c.due_date, data.today)}`}
                  </p>
                </div>
                <p className="bill__amount">{peso(c.amount)}</p>
                <button type="button" className="btn btn--small" onClick={() => navigate(c.kind === "utang" ? "/utang" : "/plan")}>
                  Open
                </button>
              </li>
            ))}
          </ul>
        )}
        {data.bills.length === 0 ? (
          <p className="muted">
            No bills before payday.{" "}
            <a href="/plan" onClick={(e) => (e.preventDefault(), navigate("/plan"))}>
              Add your bills
            </a>
          </p>
        ) : (
          <ul className="list">
            {data.bills.map((b) => (
              <li key={`${b.bill_id}-${b.due_date}`} className={`bill${b.paid ? " is-paid" : ""}`}>
                <div>
                  <p className="bill__name">{b.name}</p>
                  <p className={`small ${b.overdue ? "danger" : "muted"}`}>
                    {b.paid ? "Paid" : b.overdue ? `Overdue since ${shortDate(b.due_date)}` : `Due ${dayLabel(b.due_date, data.today)}`}
                  </p>
                </div>
                <p className="bill__amount">{peso(b.amount)}</p>
                {!b.paid && (
                  <button
                    type="button"
                    className="btn btn--small"
                    disabled={paying !== null}
                    onClick={() => pay(b.bill_id, b.due_date)}
                  >
                    {paying === `${b.bill_id}-${b.due_date}` ? "…" : "Pay"}
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      {data.cycle_spending.length > 0 && (
        <section className="card">
          <h2 className="card__title">Spent this cycle</h2>
          <ul className="bars">
            {data.cycle_spending.map((c) => (
              <li key={c.name}>
                <span className="bars__label">
                  <span aria-hidden="true">{c.emoji}</span> {c.name}
                </span>
                <span className="bars__track" aria-hidden="true">
                  <span style={{ width: `${(toCentavos(c.total) / maxSpend) * 100}%` }} />
                </span>
                <span className="bars__value">{peso(c.total, { round: true })}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="card">
        <div className="card__head">
          <h2 className="card__title">Recent</h2>
          <a href="/activity" onClick={(e) => (e.preventDefault(), navigate("/activity"))}>
            See all
          </a>
        </div>
        {data.recent.length ? (
          <ul className="list">
            {data.recent.map((t) => (
              <TxnRow key={t.id} txn={t} today={data.today} onClick={() => onEdit(t)} />
            ))}
          </ul>
        ) : (
          <p className="muted">Nothing yet. Tap + and try “kape 150 gcash”.</p>
        )}
      </section>
    </div>
  );
}
