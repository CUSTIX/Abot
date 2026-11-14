from django.urls import path
from rest_framework.routers import SimpleRouter

from planning import views

router = SimpleRouter()
router.register("bills", views.BillViewSet, basename="bill")
router.register("split-rules", views.SplitRuleViewSet, basename="split-rule")
router.register("goals", views.GoalViewSet, basename="goal")

urlpatterns = [
    path("today/", views.TodayView.as_view(), name="today"),
    path("schedule/", views.ScheduleView.as_view(), name="schedule"),
    path("payday/", views.PaydayView.as_view(), name="payday"),
    path("report/", views.ReportView.as_view(), name="report"),
    *router.urls,
]
