# Sahod

Payday-first money app for Filipinos. "Know what's safe to spend until sahod."

## Goal (read this first)

**Portfolio project**, sibling of RestoCore. A hiring manager should be able to:
1. Clone, `docker compose up`, open the app, log in as the demo user.
2. Click through a live or recorded demo.
3. Read the README and see clear decisions, tests on both sides, and CI.

A small thing that works end to end beats a big thing half built. Everything is **free to build
and run**: no paid services or APIs.

## The idea

Most budget apps plan by month. Many Filipinos are paid twice a month (kinsenas: 15th and 30th)
and money runs out *between paydays*. Sahod plans per pay cycle:

- **Safe to spend today**: spendable money minus unpaid bills due before the next payday,
  spread over the days left. The home screen.
- **Payday split**: when salary arrives, split it into wallets/expenses by rules (bills, savings,
  padala, spending).
- **Wallets** people actually use: GCash, Maya, cash, bank; transfers between them.
- **Quick add**: `kape 150 gcash` → expense of ₱150, Food & drinks, from GCash.
- **Utang** (who owes whom, partial payments) and **paluwagan** (rotating savings groups).
  Their money moves are *neutral* transactions: they change balances, never count as spending.

## Stack

- Backend: Django 5.2 + Django REST Framework, PostgreSQL 17.
- Frontend: React 19 + TypeScript + Vite, installable PWA. Served by Django in production
  (one container, same origin, session auth + CSRF, no CORS or JWT).
- Docker Compose for dev and prod parity. pytest + ruff; Vitest + ESLint + tsc.
- GitHub Actions CI.

## Layout

```
config/      settings, urls, SPA + health views
core/        shared base model, security headers, helpers
accounts/    custom User, auth API (csrf, signup, login, logout, me)
money/       wallets, categories, transactions, transfers
planning/    pay schedule, bills, split rules, safe-to-spend, payday split
utang/       lending/borrowing with partial payments (neutral money moves)
paluwagan/   rotating savings groups (neutral money moves)
frontend/    React app (src/), Vite config, Vitest tests
```

Every Django app: `models.py`, `services.py` (writes and business rules), `selectors.py` (reads),
`serializers.py`, `views.py`, `urls.py`, `admin.py`, `tests/`. An app does not reach into another
app's models for writes; call its services.

## Commands

```
cp .env.example .env                 # first time (Windows cmd: copy .env.example .env)
docker compose up --build            # API on :8001, React dev server on http://localhost:5173
docker compose run --rm api python manage.py seed_demo   # demo user + fake data
docker compose run --rm api pytest
docker compose run --rm api ruff check .
docker compose run --rm api ruff format --check .
docker compose run --rm frontend npm test        # Vitest
docker compose run --rm frontend npm run lint    # ESLint + tsc
docker compose -f docker-compose.prod.yml -p sahod-prod up --build -d   # production-style on :8081
```

If a command here is wrong or missing, fix this file in the same change.

## Rules for code

- Money is `Decimal` in Python and integer centavos or strings in TypeScript. Never float math.
- Every query is scoped to the signed-in user (`owner=request.user`). Another user's object is a
  404, never a 403, so ids can't be probed. Each endpoint has a cross-user test.
- Business rules live in `services.py` / pure functions with unit tests (`planning/cycle.py`).
- `transaction.atomic()` when several writes must succeed together (payday split).
- Config and secrets from environment variables. Commit `.env.example` only.
- Demo data from Faker; never real names or real finances.
- No inline JavaScript in Django templates; the CSP blocks it.

## Git rules

- Stage explicit paths only. Show the diff before every commit. Short imperative messages.
- Never push without the owner confirming in that moment.
