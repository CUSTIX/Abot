#!/bin/sh
# Production entrypoint: prepare the database, optionally reset the public demo, start gunicorn.
set -e
python manage.py migrate --noinput
python manage.py createcachetable  # throttle counters live in Postgres
if [ "${DEMO_RESET_ON_START:-false}" = "true" ]; then
  python manage.py seed_demo --reset
fi
exec gunicorn config.wsgi:application \
  --bind "0.0.0.0:${PORT:-8000}" \
  --workers "${WEB_CONCURRENCY:-2}" \
  --timeout 30 \
  --access-logfile - --error-logfile -
