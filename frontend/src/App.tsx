import { useEffect, useState } from "react";
import { api, refreshCsrf } from "./lib/api";
import { navigate, useRoute } from "./lib/router";
import type { Route } from "./lib/router";
import { StoreProvider, useStore } from "./lib/store";
import type { Transaction, User } from "./lib/types";
import { Sheet } from "./components/Sheet";
import { TransactionForm } from "./components/TransactionForm";
import { Activity } from "./pages/Activity";
import { Login } from "./pages/Login";
import { Plan } from "./pages/Plan";
import { Today } from "./pages/Today";
import { Utang } from "./pages/Utang";
import { Wallets } from "./pages/Wallets";

const TABS: { route: Route; label: string; icon: string }[] = [
  { route: "/", label: "Today", icon: "☀" },
  { route: "/activity", label: "Activity", icon: "☰" },
  { route: "/wallets", label: "Wallets", icon: "◫" },
  { route: "/plan", label: "Plan", icon: "◷" },
];
const TITLES: Record<string, string> = {
  "/": "Today",
  "/activity": "Activity",
  "/wallets": "Wallets",
  "/plan": "Plan",
  "/utang": "Utang",
};

export function App() {
  const route = useRoute();
  const [user, setUser] = useState<User | null | undefined>(undefined);

  useEffect(() => {
    refreshCsrf()
      .then(() => api<{ user: User | null }>("auth/me/"))
      .then((me) => setUser(me.user))
      .catch(() => setUser(null));
  }, []);

  useEffect(() => {
    if (user === null && route !== "/login" && route !== "/signup") navigate("/login", true);
  }, [user, route]);

  if (user === undefined) return <div className="boot" aria-busy="true" />;
  if (user === null || route === "/login" || route === "/signup") {
    return <Login mode={route === "/signup" ? "signup" : "login"} onSignedIn={setUser} />;
  }
  return (
    <StoreProvider>
      <Shell user={user} route={route} onSignedOut={() => setUser(null)} />
    </StoreProvider>
  );
}

function Shell({ user, route, onSignedOut }: { user: User; route: Route; onSignedOut: () => void }) {
  const { message } = useStore();
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<Transaction | null>(null);
  // Utang and paluwagan moves are managed on their own screens, not as plain transactions.
  const edit = (txn: Transaction) =>
    txn.source ? navigate(txn.source === "utang" ? "/utang" : "/plan") : setEditing(txn);

  async function logout() {
    await api("auth/logout/", "POST").catch(() => undefined);
    await refreshCsrf();
    onSignedOut();
    navigate("/login", true);
  }

  return (
    <div className="app">
      <header className="topbar">
        <div className="topbar__brand">
          <span className="logo logo--small" aria-hidden="true">₱</span>
          <span>{TITLES[route] ?? "Sahod"}</span>
        </div>
        <div className="topbar__user">
          <span className="muted small">{user.first_name || user.username}</span>
          <button type="button" className="link-btn" onClick={logout}>
            Log out
          </button>
        </div>
      </header>

      <main className="content" id="main">
        {route === "/" && <Today onEdit={edit} />}
        {route === "/activity" && <Activity onEdit={edit} />}
        {route === "/wallets" && <Wallets />}
        {route === "/plan" && <Plan />}
        {route === "/utang" && <Utang />}
      </main>

      <nav className="tabbar" aria-label="Main">
        {TABS.slice(0, 2).map((t) => (
          <Tab key={t.route} {...t} active={route === t.route} />
        ))}
        <button type="button" className="tabbar__add" onClick={() => setAdding(true)} aria-label="Add a transaction">
          ＋
        </button>
        {TABS.slice(2).map((t) => (
          <Tab key={t.route} {...t} active={route === t.route || (t.route === "/plan" && route === "/utang")} />
        ))}
      </nav>

      <Sheet open={adding} title="Add" onClose={() => setAdding(false)}>
        <TransactionForm onDone={() => setAdding(false)} />
      </Sheet>
      <Sheet open={editing !== null} title="Edit" onClose={() => setEditing(null)}>
        {editing && <TransactionForm key={editing.id} initial={editing} onDone={() => setEditing(null)} />}
      </Sheet>

      <div className={`toast${message ? " is-on" : ""}`} role="status" aria-live="polite">
        {message}
      </div>
    </div>
  );
}

function Tab({ route, label, icon, active }: { route: Route; label: string; icon: string; active: boolean }) {
  return (
    <a
      href={route}
      className={`tab${active ? " is-on" : ""}`}
      aria-current={active ? "page" : undefined}
      onClick={(e) => {
        e.preventDefault();
        navigate(route);
      }}
    >
      <span className="tab__icon" aria-hidden="true">
        {icon}
      </span>
      {label}
    </a>
  );
}
