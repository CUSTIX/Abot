import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { dayLabel, isoDate } from "../lib/dates";
import { peso, toCentavos } from "../lib/money";
import { useStore } from "../lib/store";
import type { Kind, Page, Transaction } from "../lib/types";
import { TxnRow } from "../components/TxnRow";

const FILTERS: { value: Kind | ""; label: string }[] = [
  { value: "", label: "All" },
  { value: "expense", label: "Spent" },
  { value: "income", label: "Received" },
  { value: "transfer", label: "Transfers" },
];

export function Activity({ onEdit }: { onEdit: (t: Transaction) => void }) {
  const { version } = useStore();
  const [kind, setKind] = useState<Kind | "">("");
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const [result, setResult] = useState<{ key: string; rows: Transaction[]; next: string | null }>({
    key: "",
    rows: [],
    next: null,
  });
  const today = isoDate(new Date());

  // Debounce typing so every keystroke isn't a request.
  useEffect(() => {
    const id = window.setTimeout(() => setSearch(query.trim()), 250);
    return () => window.clearTimeout(id);
  }, [query]);

  // The result remembers which filters it was loaded for, so "loading" is derived, not stored.
  const key = `${kind}|${search}|${version}`;
  const loading = result.key !== key;
  const { rows, next } = result;

  useEffect(() => {
    let live = true;
    const params = new URLSearchParams();
    if (kind) params.set("kind", kind);
    if (search) params.set("q", search);
    api<Page<Transaction>>(`transactions/?${params}`)
      .then((page) => live && setResult({ key, rows: page.results, next: page.next }))
      .catch(() => live && setResult({ key, rows: [], next: null }));
    return () => {
      live = false;
    };
  }, [kind, search, key]);

  async function loadMore() {
    if (!next) return;
    const url = new URL(next, window.location.origin);
    const page = await api<Page<Transaction>>(`transactions/${url.search}`);
    setResult((r) => ({ ...r, rows: [...r.rows, ...page.results], next: page.next }));
  }

  const groups = new Map<string, Transaction[]>();
  for (const t of rows) groups.set(t.date, [...(groups.get(t.date) ?? []), t]);

  return (
    <div className="stack">
      <div className="toolbar">
        <input
          type="search"
          className="search"
          placeholder="Search notes or categories"
          aria-label="Search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <div className="segmented" role="radiogroup" aria-label="Show">
          {FILTERS.map((f) => (
            <button
              key={f.value}
              type="button"
              role="radio"
              aria-checked={kind === f.value}
              className={kind === f.value ? "is-on" : ""}
              onClick={() => setKind(f.value)}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      <p className="export">
        <a href="/api/export.csv" download>
          Export all to CSV
        </a>
        <span className="muted small"> · opens in Excel or Google Sheets</span>
      </p>

      {!loading && rows.length === 0 && (
        <p className="empty">{search || kind ? "Nothing matches." : "No transactions yet."}</p>
      )}

      {[...groups.entries()].map(([date, txns]) => {
        const out = txns
          .filter((t) => t.kind === "expense")
          .reduce((sum, t) => sum + toCentavos(t.amount), 0);
        return (
          <section key={date} className="card day">
            <header className="day__head">
              <h2>{dayLabel(date, today)}</h2>
              {out > 0 && <span className="muted small">−{peso(out)}</span>}
            </header>
            <ul className="list">
              {txns.map((t) => (
                <TxnRow key={t.id} txn={t} today={today} showDate={false} onClick={() => onEdit(t)} />
              ))}
            </ul>
          </section>
        );
      })}

      {next && (
        <button type="button" className="btn btn--ghost btn--block" onClick={loadMore}>
          Load more
        </button>
      )}
    </div>
  );
}
