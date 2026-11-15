#!/bin/sh
# Production entrypoint: prepare the database, optionally reset the public demo, start gunicorn.
set -e
python manage.py migrate --noinput
python manage.py createcachetable  # throttle counters live in Postgres

# Public demo only: fresh demo data, and visitor sign-ups are wiped (nothing typed in is kept).
# Both flags are required so a copied environment file can never wipe a real database.
if [ "${DEMO_RESET_ON_START:-false}" = "true" ] && [ "${DEMO_MODE:-false}" = "true" ]; then
  python manage.py seed_demo --reset --wipe-visitors

  # The live demo is kept awake (.github/workflows/keep-awake.yml), so it rarely restarts. Reset
  # it once a day as well, at DEMO_RESET_HOUR local time, in a background loop next to gunicorn.
  # The reset is one transaction, so visitors never see an empty database.
  if [ -n "${DEMO_RESET_HOUR:-}" ]; then
    if python bin/seconds_until_hour.py "$DEMO_RESET_HOUR" > /dev/null; then
      (
        while true; do
          sleep "$(python bin/seconds_until_hour.py "$DEMO_RESET_HOUR")"
          python manage.py seed_demo --reset --wipe-visitors || echo "Nightly demo reset failed" >&2
        done
      ) &
    else
      echo "Nightly demo reset disabled: DEMO_RESET_HOUR='$DEMO_RESET_HOUR' is not a whole hour 0-23." >&2
    fi
  fi
elif [ "${DEMO_RESET_ON_START:-false}" = "true" ]; then
  echo "DEMO_RESET_ON_START ignored: it only works together with DEMO_MODE=true." >&2
fi

# Threads keep the site answering during a slow request; recycling workers caps memory growth on a
# small instance. The access log records the path but not the query string.
exec gunicorn config.wsgi:application \
  --bind "0.0.0.0:${PORT:-8000}" \
  --workers "${WEB_CONCURRENCY:-2}" \
  --worker-class gthread --threads 4 \
  --worker-tmp-dir /dev/shm \
  --max-requests 1000 --max-requests-jitter 100 \
  --timeout 30 --graceful-timeout 30 \
  --access-logfile - --error-logfile - \
  --access-logformat '%(h)s "%(m)s %(U)s" %(s)s %(b)s %(L)s'
