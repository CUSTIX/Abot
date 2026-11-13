# Three stages:
#   frontend - builds the React app with Node (only its static output is kept)
#   dev      - Python + test tools, Django dev server (docker-compose.yml)
#   prod     - runtime deps, the built React app, collected static files, gunicorn

FROM node:22-slim AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN useradd --create-home appuser

FROM base AS dev
COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY . .
USER appuser
EXPOSE 8000
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

FROM base AS prod
COPY . .
COPY --from=frontend /frontend/dist /app/frontend/dist
RUN DJANGO_SECRET_KEY=build-only-not-secret DJANGO_STATIC_MANIFEST=true \
    python manage.py collectstatic --noinput \
 && chown -R appuser:appuser /app/staticfiles
USER appuser
EXPOSE 8000
CMD ["sh", "bin/start.sh"]
