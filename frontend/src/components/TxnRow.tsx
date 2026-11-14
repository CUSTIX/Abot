import { dayLabel } from "../lib/dates";
import { peso } from "../lib/money";
import type { Transaction } from "../lib/types";

export function TxnRow({
  txn,
  today,
  onClick,
  showDate = true,
}: {
  txn: Transaction;
  today: string;
  onClick: () => void;
  showDate?: boolean;
}) {
  const title =
    txn.kind === "transfer"
      ? `${txn.wallet_name} → ${txn.to_wallet_name}`
      : txn.note || txn.category_name || (txn.kind === "income" ? "Income" : "Expense");
  const meta = [
    txn.kind === "transfer"
      ? "Transfer"
      : txn.source === "utang"
        ? "Utang"
        : txn.source === "paluwagan"
          ? "Paluwagan"
          : (txn.category_name ?? "Uncategorised"),
    txn.kind === "transfer" ? null : txn.wallet_name,
    showDate ? dayLabel(txn.date, today) : null,
  ]
    .filter(Boolean)
    .join(" · ");
  const sign = txn.kind === "income" ? "+" : txn.kind === "expense" ? "−" : "";

  return (
    <li>
      <button type="button" className="txn" onClick={onClick}>
        <span className={`txn__icon txn__icon--${txn.neutral ? "transfer" : txn.kind}`} aria-hidden="true">
          {txn.kind === "transfer" ? "⇄" : txn.source === "utang" ? "🤝" : txn.source === "paluwagan" ? "🪙" : txn.category_emoji || (txn.kind === "income" ? "＋" : "•")}
        </span>
        <span className="txn__text">
          <span className="txn__title">{title}</span>
          <span className="txn__meta">{meta}</span>
        </span>
        <span className={`txn__amount txn__amount--${txn.neutral ? "neutral" : txn.kind}`}>
          {sign}
          {peso(txn.amount)}
        </span>
      </button>
    </li>
  );
}
