# Security

Abot is a portfolio project. The public demo holds only fake data and resets on every start.

## Reporting a problem

Please open a private security advisory on the GitHub repository (Security → Report a
vulnerability) instead of a public issue.

## What protects what

**Your data stays yours**
- Every query is scoped to the signed-in user. Asking for someone else's wallet, transaction,
  bill, utang or paluwagan by id returns **404**, not 403, so ids can't be probed.
- Related ids in a request body (a wallet or category) only resolve among your own rows
  (`core.api.OwnedPrimaryKeyField`); services check ownership again before writing.
- Tests try each of these across two users, and a test walks every `/api/` URL to prove it needs a
  signed-in user.

**Sign-in**
- Session cookies (HttpOnly, SameSite=Lax, Secure on HTTPS). No tokens in localStorage.
- CSRF is enforced on every write **and on login/sign-up** (DRF skips CSRF for anonymous
  requests by default, which would allow login CSRF). The CSRF cookie is HttpOnly; the app gets
  the token from `/api/auth/csrf/` and keeps it in memory.
- Login (10/min) and sign-up (5/hour) are rate limited. Counters live in Postgres, so every
  worker shares them. The visitor IP comes only from a header the proxy overwrites
  (`CLIENT_IP_HEADER`); a forged `X-Forwarded-For` can't buy extra attempts (tested).
- Django's password validators (length, common passwords, similarity, all-numeric).

**Browser**
- Content Security Policy: `script-src 'self'` (no inline scripts or eval), `object-src 'none'`,
  `frame-ancestors 'none'`, `base-uri 'none'`. React escapes all text; raw HTML rendering is
  banned by an ESLint rule.
- `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy: same-origin`, a restrictive
  `Permissions-Policy`, and `Cache-Control: no-store` on every signed-in response.
- The service worker caches only the app shell and fingerprinted static files, **never** `/api/`.

**Money correctness**
- Decimal everywhere in Python, integer centavos in TypeScript. Balances are derived from the
  ledger, never stored.
- Multi-step writes (payday split, bill payment, utang and paluwagan moves) run in one database
  transaction; double taps hit row locks or unique constraints, not duplicate money.

**Supply chain and CI**
- Every dependency is pinned. CI runs `pip-audit` and `npm audit`, ruff's security rules, CodeQL
  (Python + TypeScript), `manage.py check --deploy` in HTTPS mode, and builds the production
  image. Dependabot proposes updates weekly.
- Secrets come only from environment variables; `.env` is gitignored.
