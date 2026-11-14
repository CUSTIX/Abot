import { useState } from "react";
import type { CSSProperties, FormEvent } from "react";
import { api, ApiError } from "../lib/api";
import { parseAmount, peso, toCentavos, toDecimalString } from "../lib/money";
import { useStore } from "../lib/store";
import type { Wallet } from "../lib/types";
import { Sheet } from "../components/Sheet";

const KIND_LABEL: Record<Wallet["kind"], string> = {
  cash: "Cash",
  ewallet: "E-wallet",
  bank: "Bank",
  savings: "Savings",
};
const COLORS = ["#0f766e", "#2563eb", "#059669", "#7c3aed", "#b45309", "#be123c", "#334155"];

export function Wallets() {
  const { wallets } = useStore();
  const [editing, setEditing] = useState<Wallet | "new" | null>(null);
  const active = wallets.filter((w) => !w.archived);
  const total = active.reduce((s, w) => s + toCentavos(w.balance), 0);
  const spendable = active.filter((w) => w.spendable).reduce((s, w) => s + toCentavos(w.balance), 0);

  return (
    <div className="stack">
      <section className="card totals">
        <div>
          <p className="eyebrow">All wallets</p>
          <p className="totals__big">{peso(total)}</p>
        </div>
        <div>
          <p className="eyebrow">Spendable</p>
          <p className="totals__mid">{peso(spendable)}</p>
        </div>
      </section>

      <ul className="wallets">
        {active.map((w) => (
          <li key={w.id}>
            <button type="button" className="wallet" style={{ "--wallet": w.color } as CSSProperties} onClick={() => setEditing(w)}>
              <span className="wallet__kind">
                {KIND_LABEL[w.kind]}
                {!w.spendable && " · not spendable"}
              </span>
              <span className="wallet__name">{w.name}</span>
              <span className="wallet__balance">{peso(w.balance)}</span>
            </button>
          </li>
        ))}
        <li>
          <button type="button" className="wallet wallet--add" onClick={() => setEditing("new")}>
            <span aria-hidden="true">＋</span> Add wallet
          </button>
        </li>
      </ul>

      <Sheet
        open={editing !== null}
        title={editing === "new" ? "New wallet" : "Edit wallet"}
        onClose={() => setEditing(null)}
      >
        {editing !== null && (
          <WalletForm wallet={editing === "new" ? null : editing} onDone={() => setEditing(null)} />
        )}
      </Sheet>
    </div>
  );
}

function WalletForm({ wallet, onDone }: { wallet: Wallet | null; onDone: () => void }) {
  const { changed, toast } = useStore();
  const [name, setName] = useState(wallet?.name ?? "");
  const [kind, setKind] = useState<Wallet["kind"]>(wallet?.kind ?? "ewallet");
  const [opening, setOpening] = useState(wallet?.opening_balance ?? "0");
  const [spendable, setSpendable] = useState(wallet?.spendable ?? true);
  const [color, setColor] = useState(wallet?.color ?? COLORS[0]!);
  const [errors, setErrors] = useState<Record<string, string[]>>({});
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    const cents = opening.trim() === "" || opening === "0" ? 0 : parseAmount(opening);
    if (cents === null) return setErrors({ opening_balance: ["Enter an amount, like 1500."] });
    setBusy(true);
    const body = { name, kind, opening_balance: toDecimalString(cents), spendable, color };
    try {
      await api(wallet ? `wallets/${wallet.id}/` : "wallets/", wallet ? "PATCH" : "POST", body);
      changed();
      toast("Saved");
      onDone();
    } catch (err) {
      setErrors(err instanceof ApiError ? err.fields : {});
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!wallet || !window.confirm(`Remove ${wallet.name}? A wallet with history is archived instead.`)) return;
    const result = await api<{ archived?: boolean } | undefined>(`wallets/${wallet.id}/`, "DELETE");
    changed();
    toast(result?.archived ? `${wallet.name} archived` : `${wallet.name} removed`);
    onDone();
  }

  return (
    <form className="form" onSubmit={submit} noValidate>
      <label className="field">
        <span>Name</span>
        <input value={name} maxLength={40} onChange={(e) => setName(e.target.value)} required />
        {errors.name && <p className="field__error">{errors.name[0]}</p>}
      </label>
      <label className="field">
        <span>Type</span>
        <select
          value={kind}
          onChange={(e) => {
            const k = e.target.value as Wallet["kind"];
            setKind(k);
            if (!wallet) setSpendable(k !== "savings");
          }}
        >
          {Object.entries(KIND_LABEL).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </label>
      <label className="field">
        <span>Starting balance</span>
        <input inputMode="decimal" value={opening} onChange={(e) => setOpening(e.target.value)} />
        {errors.opening_balance && <p className="field__error">{errors.opening_balance[0]}</p>}
      </label>
      <label className="check">
        <input type="checkbox" checked={spendable} onChange={(e) => setSpendable(e.target.checked)} />
        <span>
          Counts as spendable
          <small className="muted"> Off for savings and emergency funds.</small>
        </span>
      </label>
      <fieldset className="field">
        <legend>Colour</legend>
        <div className="swatches">
          {COLORS.map((c) => (
            <button
              key={c}
              type="button"
              className={`swatch${color === c ? " is-on" : ""}`}
              style={{ background: c }}
              aria-label={`Colour ${c}`}
              aria-pressed={color === c}
              onClick={() => setColor(c)}
            />
          ))}
        </div>
      </fieldset>
      <div className="form__actions">
        {wallet && (
          <button type="button" className="btn btn--ghost btn--danger" onClick={remove}>
            Remove
          </button>
        )}
        <button className="btn btn--primary" disabled={busy || !name.trim()}>
          {busy ? "Saving…" : "Save"}
        </button>
      </div>
    </form>
  );
}
