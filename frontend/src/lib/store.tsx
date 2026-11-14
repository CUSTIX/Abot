/* App-wide data that rarely changes (wallets, categories) plus a "changed" counter that screens
   watch to reload after any write. */
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { api } from "./api";
import type { Category, Wallet } from "./types";

interface Store {
  wallets: Wallet[];
  categories: Category[];
  version: number;
  changed: () => void;
  toast: (message: string) => void;
  message: string | null;
}

const StoreContext = createContext<Store | null>(null);

export function StoreProvider({ children }: { children: ReactNode }) {
  const [wallets, setWallets] = useState<Wallet[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [version, setVersion] = useState(0);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    Promise.all([api<Wallet[]>("wallets/"), api<Category[]>("categories/")])
      .then(([w, c]) => {
        if (!live) return;
        setWallets(w);
        setCategories(c);
      })
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, [version]);

  const changed = useCallback(() => setVersion((v) => v + 1), []);
  const toast = useCallback((text: string) => {
    setMessage(text);
    window.setTimeout(() => setMessage((m) => (m === text ? null : m)), 3200);
  }, []);

  const value = useMemo(
    () => ({ wallets, categories, version, changed, toast, message }),
    [wallets, categories, version, changed, toast, message],
  );
  return <StoreContext.Provider value={value}>{children}</StoreContext.Provider>;
}

export function useStore(): Store {
  const store = useContext(StoreContext);
  if (!store) throw new Error("useStore outside StoreProvider");
  return store;
}

/** Load something from the API and reload it whenever data changes anywhere. */
export function useLoad<T>(path: string | null): { data: T | null; error: string | null } {
  const { version } = useStore();
  const [state, setState] = useState<{ data: T | null; error: string | null }>({
    data: null,
    error: null,
  });
  useEffect(() => {
    if (!path) return;
    let live = true;
    api<T>(path)
      .then((data) => live && setState({ data, error: null }))
      .catch((e: Error) => live && setState((s) => ({ data: s.data, error: e.message })));
    return () => {
      live = false;
    };
  }, [path, version]);
  return state;
}
