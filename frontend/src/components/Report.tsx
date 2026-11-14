import { isoDate, shortDate } from "../lib/dates";
import { peso, toCentavos } from "../lib/money";
import { useLoad } from "../lib/store";
import type { CycleReport, Transaction } from "../lib/types";
import { TxnRow } from "./TxnRow";

/* This pay cycle so far, next to the whole previous one. */
export function Report({ onEdit }: { onEdit: (t: Transaction) => void }) {
  const { data } = useLoad<CycleReport>("report/");
  if (!data) return <div className="card skeleton" />;
  const today = isoDate(new Date());
  const spent = toCentavos(data.spending);
  const before = toCentavos(data.previous.spending);
  // Compare like with like: the previous cycle's pace over the same number of days.
  const beforePace = Math.round((before / Math.max(data.previous.days, 1)) * data.days);
  const diff = beforePace > 0 ? Math.round(((spent - beforePace) / beforePace) * 100) : null;
  const max = Math.max(1, ...data.categories.flatMap((c) => [toCentavos(c.total), toCentavos(c.previous)]));

  return (
    <div className="stack">
      <section className="card report-head">
        <p className="eyebrow">
          This cycle · {shortDate(data.start)} – {shortDate(data.end)} · day {data.days}
        </p>
        <div className="report-head__grid">
          <div>
            <span className="muted small">Received</span>
            <strong>{peso(data.income, { round: true })}</strong>
          </div>
          <div>
            <span className="muted small">Spent</span>
            <strong>{peso(data.spending, { round: true })}</strong>
          </div>
          <div>
            <span className="muted small">Kept</span>
            <strong className={toCentavos(data.kept) < 0 ? "danger" : "good"}>{peso(data.kept, { round: true })}</strong>
          </div>
        </div>
        <p className="report-head__note">
          {peso(data.daily_average, { round: true })} a day on average.{" "}
          {diff === null
            ? ""
            : diff <= 0
              ? `That's ${Math.abs(diff)}% less than last cycle at this point. Nice.`
              : `That's ${diff}% more than last cycle at this point.`}
        </p>
      </section>

      {data.categories.length > 0 && (
        <section className="card">
          <h2 className="card__title">By category</h2>
          <p className="muted small legend">
            <span className="legend__now" /> this cycle <span className="legend__before" /> last cycle (whole)
          </p>
          <ul className="compare">
            {data.categories.map((c) => (
              <li key={c.name}>
                <span className="compare__label">
                  <span aria-hidden="true">{c.emoji}</span> {c.name}
                </span>
                <span className="compare__bars" aria-hidden="true">
                  <span className="compare__now" style={{ width: `${(toCentavos(c.total) / max) * 100}%` }} />
                  <span className="compare__before" style={{ width: `${(toCentavos(c.previous) / max) * 100}%` }} />
                </span>
                <span className="compare__value">
                  {peso(c.total, { round: true })}
                  <small>{peso(c.previous, { round: true })}</small>
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {data.biggest.length > 0 && (
        <section className="card">
          <h2 className="card__title">Biggest this cycle</h2>
          <ul className="list">
            {data.biggest.map((t) => (
              <TxnRow key={t.id} txn={t} today={today} onClick={() => onEdit(t)} />
            ))}
          </ul>
        </section>
      )}

      <section className="card report-prev">
        <h2 className="card__title">Last cycle</h2>
        <p className="muted small">
          {shortDate(data.previous.start)} – {shortDate(data.previous.end)}: received {peso(data.previous.income, { round: true })},
          spent {peso(data.previous.spending, { round: true })}, kept{" "}
          <strong>{peso(data.previous.kept, { round: true })}</strong>.
        </p>
      </section>
    </div>
  );
}
