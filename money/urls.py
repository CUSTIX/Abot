from django.urls import path
from rest_framework.routers import SimpleRouter

from money import views

router = SimpleRouter()
router.register("wallets", views.WalletViewSet, basename="wallet")
router.register("categories", views.CategoryViewSet, basename="category")
router.register("transactions", views.TransactionViewSet, basename="transaction")

urlpatterns = [
    path("spending/", views.SpendingView.as_view(), name="spending"),
    *router.urls,
]
