"""Root API router, aggregating each domain app's own viewsets. Mounted
under /api/v1/ by config/urls.py.
"""

from rest_framework.routers import DefaultRouter

from apps.catalog.api.viewsets import ProductViewSet
from apps.partners.api.viewsets import PartnerViewSet

router = DefaultRouter()
router.register("partners", PartnerViewSet, basename="partner")
router.register("products", ProductViewSet, basename="product")

urlpatterns = router.urls
