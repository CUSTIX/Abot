/* A tiny router: five screens don't need a routing library. */
import { useEffect, useState } from "react";

export type Route =
  | "/"
  | "/activity"
  | "/wallets"
  | "/plan"
  | "/utang"
  | "/paluwagan"
  | "/login"
  | "/signup";
const ROUTES: Route[] = ["/", "/activity", "/wallets", "/plan", "/utang", "/paluwagan", "/login", "/signup"];

function current(): Route {
  const path = window.location.pathname.replace(/\/+$/, "") || "/";
  return (ROUTES as string[]).includes(path) ? (path as Route) : "/";
}

export function navigate(to: Route, replace = false): void {
  if (to === window.location.pathname) return;
  window.history[replace ? "replaceState" : "pushState"]({}, "", to);
  window.dispatchEvent(new PopStateEvent("popstate"));
  window.scrollTo({ top: 0 });
}

export function useRoute(): Route {
  const [route, setRoute] = useState<Route>(current);
  useEffect(() => {
    const onPop = () => setRoute(current());
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);
  return route;
}
