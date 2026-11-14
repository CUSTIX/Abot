import { useState } from "react";
import type { FormEvent } from "react";
import { api, ApiError, getDemoLogin, refreshCsrf } from "../lib/api";
import { navigate } from "../lib/router";
import type { User } from "../lib/types";

export function Login({ mode, onSignedIn }: { mode: "login" | "signup"; onSignedIn: (u: User) => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [errors, setErrors] = useState<Record<string, string[]>>({});
  const [busy, setBusy] = useState(false);
  const signup = mode === "signup";

  async function submit(e: FormEvent, demo = false) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setErrors({});
    try {
      const body = demo
        ? getDemoLogin()
        : signup
          ? { username, password, first_name: name }
          : { username, password };
      const user = await api<User>(signup && !demo ? "auth/signup/" : "auth/login/", "POST", body);
      await refreshCsrf(); // signing in rotates the CSRF token
      onSignedIn(user);
      navigate("/", true);
    } catch (err) {
      setErrors(err instanceof ApiError ? err.fields : { detail: ["Something went wrong."] });
    } finally {
      setBusy(false);
    }
  }

  const err = (f: string) =>
    errors[f]?.[0] ? (
      <p className="field__error" role="alert">
        {errors[f]?.[0]}
      </p>
    ) : null;

  return (
    <main className="auth">
      <div className="auth__brand">
        <span className="logo" aria-hidden="true">₱</span>
        <h1>Sahod</h1>
        <p>Know what's safe to spend until your next payday.</p>
      </div>
      <form className="card form" onSubmit={(e) => submit(e)} noValidate>
        <h2>{signup ? "Create your account" : "Welcome back"}</h2>
        {signup && (
          <label className="field">
            <span>First name (optional)</span>
            <input value={name} onChange={(e) => setName(e.target.value)} autoComplete="given-name" />
          </label>
        )}
        <label className="field">
          <span>Username</span>
          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            autoCapitalize="none"
            required
          />
          {err("username")}
        </label>
        <label className="field">
          <span>Password</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete={signup ? "new-password" : "current-password"}
            required
          />
          {err("password")}
        </label>
        {errors.detail && (
          <p className="alert" role="alert">
            {errors.detail[0]}
          </p>
        )}
        <button className="btn btn--primary btn--block" disabled={busy}>
          {busy ? "One moment…" : signup ? "Create account" : "Log in"}
        </button>
        {getDemoLogin() && !signup && (
          <button type="button" className="btn btn--accent btn--block" disabled={busy} onClick={(e) => submit(e, true)}>
            Try the demo account
          </button>
        )}
        <p className="muted small center">
          {signup ? "Already have an account? " : "New here? "}
          <a
            href={signup ? "/login" : "/signup"}
            onClick={(e) => {
              e.preventDefault();
              navigate(signup ? "/login" : "/signup");
            }}
          >
            {signup ? "Log in" : "Create an account"}
          </a>
        </p>
      </form>
    </main>
  );
}
