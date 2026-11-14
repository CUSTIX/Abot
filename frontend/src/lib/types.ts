export type Kind = "expense" | "income" | "transfer";

export interface User {
  id: number;
  username: string;
  first_name: string;
  is_demo: boolean;
}

export interface Wallet {
  id: number;
  name: string;
  kind: "cash" | "ewallet" | "bank" | "savings";
  opening_balance: string;
  spendable: boolean;
  color: string;
  archived: boolean;
  sort_order: number;
  balance: string;
}

export interface Category {
  id: number;
  name: string;
  kind: "expense" | "income";
  emoji: string;
  keywords: string;
  archived: boolean;
}

export interface Transaction {
  id: number;
  kind: Kind;
  amount: string;
  date: string;
  wallet: number;
  to_wallet: number | null;
  category: number | null;
  note: string;
  neutral: boolean;
  source: "" | "utang" | "paluwagan";
  wallet_name: string;
  to_wallet_name: string | null;
  category_name: string | null;
  category_emoji: string;
}

export interface Page<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface BillRow {
  bill_id: number;
  name: string;
  amount: string;
  due_date: string;
  paid: boolean;
  overdue: boolean;
  payment_id: number | null;
}

export interface Today {
  has_schedule: boolean;
  today: string;
  cycle_start: string;
  next_payday: string;
  days_left: number;
  status: "ok" | "tight" | "over" | "short";
  spendable: string;
  bills_reserved: string;
  keep_aside: string;
  spent_today: string;
  per_day: string;
  left_today: string;
  free_until_payday: string;
  bills: BillRow[];
  commitments: Commitment[];
  cycle_spending: { category_id: number | null; name: string; emoji: string; total: string }[];
  recent: Transaction[];
}

export interface Schedule {
  frequency: "semi_monthly" | "monthly" | "weekly";
  first_day: number;
  second_day: number;
  weekday: number;
  weekend_rule: "before" | "after" | "none";
  expected_pay: string;
  keep_aside: string;
}

export interface Bill {
  id: number;
  name: string;
  amount: string;
  due_day: number;
  wallet: number;
  category: number | null;
  active: boolean;
}

export interface SplitRule {
  id: number;
  name: string;
  mode: "fixed" | "percent";
  value: string;
  to_wallet: number | null;
  category: number | null;
  sort_order: number;
  active: boolean;
}

export interface UtangPayment {
  id: number;
  amount: string;
  date: string;
}

export interface Utang {
  id: number;
  person: string;
  direction: "lent" | "borrowed";
  amount: string;
  date: string;
  due_date: string | null;
  note: string;
  paid: string;
  remaining: string;
  payments: UtangPayment[];
}

export interface Commitment {
  kind: "utang" | "paluwagan";
  id: number;
  label: string;
  amount: string;
  due_date: string;
  overdue: boolean;
}

export interface PaluwaganRound {
  round: number;
  date: string;
  paid: boolean;
  my_turn: boolean;
  received: boolean;
  contribution_id: number | null;
  payout_id: number | null;
}

export interface Paluwagan {
  id: number;
  name: string;
  share: string;
  members: number;
  my_turn: number;
  frequency: "payday" | "weekly" | "monthly";
  start_date: string;
  wallet: number;
  pot: string;
  contributed: string;
  total_to_pay: string;
  my_turn_date: string;
  received: boolean;
  finished: boolean;
  behind: number;
  next_due: { round: number; date: string } | null;
  rounds: PaluwaganRound[];
}

export interface Goal {
  id: number;
  name: string;
  emoji: string;
  target: string;
  target_date: string;
  wallet: number;
  wallet_name: string;
  saved: string;
  missing: string;
  paydays_left: number;
  per_payday: string;
  status: "saving" | "done" | "late";
}

export interface CycleReport {
  start: string;
  end: string;
  next_payday: string;
  days: number;
  income: string;
  spending: string;
  kept: string;
  daily_average: string;
  categories: { name: string; emoji: string; total: string; previous: string }[];
  biggest: Transaction[];
  previous: { start: string; end: string; days: number; income: string; spending: string; kept: string };
}
