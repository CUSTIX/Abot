from django.urls import path
from rest_framework.routers import SimpleRouter

from utang import views

router = SimpleRouter()
router.register("utang", views.UtangViewSet, basename="utang")

urlpatterns = [
    path("utang-summary/", views.UtangSummaryView.as_view(), name="utang-summary"),
    *router.urls,
]
