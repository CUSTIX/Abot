from django.contrib import admin
from django.urls import include, path, re_path

from config import views

urlpatterns = [
    path("api/auth/", include("accounts.urls")),
    path("api/", include("money.urls")),
    path("api/", include("planning.urls")),
    path("api/", include("utang.urls")),
    path("admin/", admin.site.urls),
    path("healthz/", views.healthz, name="healthz"),
    path("sw.js", views.service_worker, name="service-worker"),
    # Everything else is a client-side route of the React app.
    re_path(r"^(?!api/|admin/|static/)(?P<path>.*)$", views.spa, name="spa"),
]
