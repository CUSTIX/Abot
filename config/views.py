from django.conf import settings
from django.db import connection
from django.http import FileResponse, Http404, HttpResponse


def healthz(request):
    """Liveness check used by Docker/CI/deploy: proves the app runs and the DB answers."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    return HttpResponse("ok", content_type="text/plain")


def livez(request):
    """Keep-awake ping: proves the web process answers without touching the database, so the
    free Neon database can still suspend when nobody uses the app."""
    return HttpResponse("ok", content_type="text/plain")


def spa(request, path=""):
    """The React app's index.html for every non-API URL (client-side routing). In development
    the app is served by Vite on :5173 instead, so this explains where to go."""
    index = settings.FRONTEND_DIST / "index.html"
    if not index.exists():
        return HttpResponse(
            "Abot API is running. In development open the React app at http://localhost:5173",
            content_type="text/plain",
        )
    response = FileResponse(index.open("rb"), content_type="text/html")
    response["Cache-Control"] = "no-cache"  # always fetch the latest build's asset names
    return response


def service_worker(request):
    """The PWA service worker must be served from the site root to control every page."""
    worker = settings.FRONTEND_DIST / "sw.js"
    if not worker.exists():
        raise Http404
    response = FileResponse(worker.open("rb"), content_type="text/javascript")
    response["Cache-Control"] = "no-cache"
    return response
