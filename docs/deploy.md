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
   - resets the demo data (`seed_demo --reset`, because `DEMO_RESET_ON_START=true`);
   - starts gunicorn on `$PORT`.

Every push to `main` redeploys (`autoDeploy: true`).

## Environment variables

| Variable | Live demo | Meaning |
|---|---|---|
| `DATABASE_URL` | Neon string | Overrides the `POSTGRES_*` values. |
| `DJANGO_SECRET_KEY` | generated | Required; the app refuses to start without it. |
| `DJANGO_HTTPS` | `true` | HTTPS redirect, secure cookies, HSTS. |
| `DJANGO_STATIC_MANIFEST` | `true` | Compressed, fingerprinted static files. |
| `DEMO_MODE` | `true` | The login screen offers the demo account. |
| `DEMO_RESET_ON_START` | `true` | Fresh fake data on every start. Demo only! |
| `DEMO_PASSWORD` | `sahod-demo` | The demo account's password. |
| `CLIENT_IP_HEADER` | `HTTP_CF_CONNECTING_IP` | Real visitor IP for rate limiting (set by Cloudflare). |
| `WEB_CONCURRENCY` | `2` | gunicorn workers (512 MB RAM on the free plan). |

`RENDER_EXTERNAL_HOSTNAME` (set by Render) is added to `ALLOWED_HOSTS` and the CSRF trusted
origins automatically.

## Check it

```bash
curl -I https://<your-app>.onrender.com/healthz/     # 200, HSTS header
```

Then open the site, press **Try the demo account**, and check the Today screen loads.
