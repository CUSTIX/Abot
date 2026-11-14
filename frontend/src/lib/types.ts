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
