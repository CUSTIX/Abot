# Deploying the free live demo (Render + Neon)

The demo runs on free tiers: a **Render** web service (Docker, sleeps after ~15 minutes idle) and a
**Neon** Postgres database. Free tiers change, so check both pricing pages before you start.

## 1. Database (Neon)

1. Create a project at <https://neon.tech> (choose a region near Singapore).
2. Copy the **direct** (non-pooled) connection string, for example
   `postgresql://user:password@ep-xxx.ap-southeast-1.aws.neon.tech/neondb?sslmode=require`.

## 2. Web service (Render)

1. Push this repository to GitHub.
2. In Render: **New → Blueprint**, pick the repository. Render reads [`render.yaml`](../render.yaml).
3. When asked for `DATABASE_URL`, paste the Neon string. `DJANGO_SECRET_KEY` is generated for you.
4. Deploy. The container's [`bin/start.sh`](../bin/start.sh):
   - runs migrations and creates the throttle cache table;
   - resets the demo data and deletes visitor sign-ups (`seed_demo --reset --wipe-visitors`,
     because `DEMO_RESET_ON_START=true`);
   - starts gunicorn on `$PORT`.

Pushes to `main` redeploy only after CI passes (`autoDeployTrigger: checksPass`). Every deploy also
resets the demo, so batch your pushes.

**Stay awake, in your own Render workspace.** Free services sleep after ~15 idle minutes (a cold
start takes about a minute). The `Keep awake` workflow pings `/livez/` every 10 minutes, which uses
about 744 of a workspace's 750 free hours a month, so put this service in a **different Render
workspace** from any other always-on service. `/livez/` skips the database so Neon can still
suspend; `/healthz/` (which queries it) is for compose and manual checks. Because the service no
longer restarts by itself, `DEMO_RESET_HOUR` resets the demo every night (one transaction, so
visitors never see an empty database).

## Environment variables

| Variable | Live demo | Meaning |
|---|---|---|
| `DATABASE_URL` | Neon string | Overrides the `POSTGRES_*` values. |
| `DJANGO_SECRET_KEY` | generated | Required; the app refuses to start without it. |
| `DJANGO_HTTPS` | `true` | HTTPS redirect, secure cookies, HSTS. |
| `DJANGO_STATIC_MANIFEST` | `true` | Compressed, fingerprinted static files. |
| `DEMO_MODE` | `true` | The login screen offers the demo account. |
| `DEMO_RESET_ON_START` | `true` | Fresh fake data on every start, and visitor sign-ups are deleted. Demo only! Also needs `DEMO_MODE=true`. |
| `DEMO_RESET_HOUR` | `4` | Also reset every night at 4 AM (`DJANGO_TIME_ZONE`). Needs `DEMO_RESET_ON_START` and `DEMO_MODE`. |
| `DEMO_PASSWORD` | `abot-demo` | The demo account's password. |
| `CLIENT_IP_HEADER` | `HTTP_CF_CONNECTING_IP` | Real visitor IP for rate limiting (set by Cloudflare). |
| `WEB_CONCURRENCY` | `2` | gunicorn workers (512 MB RAM on the free plan). |

`RENDER_EXTERNAL_HOSTNAME` (set by Render) is added to `ALLOWED_HOSTS` and the CSRF trusted
origins automatically.

## Check it

```bash
curl -I https://<your-app>.onrender.com/livez/       # 200, HSTS header
```

Then open the site, press **Try the demo account**, and check the Today screen loads.
