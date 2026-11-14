from rest_framework.routers import SimpleRouter

from paluwagan import views

router = SimpleRouter()
router.register("paluwagan", views.PaluwaganViewSet, basename="paluwagan")

urlpatterns = router.urls
