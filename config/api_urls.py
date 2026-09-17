"""Root API router, aggregating each domain app's own viewsets. Mounted
under /api/v1/ by config/urls.py.
"""

from rest_framework.routers import DefaultRouter

from apps.catalog.api.viewsets import ProductViewSet
from apps.partners.api.viewsets import PartnerViewSet
from apps.sales.api.viewsets import SalesInvoiceLineViewSet, SalesInvoiceViewSet

router = DefaultRouter()
router.register("partners", PartnerViewSet, basename="partner")
router.register("products", ProductViewSet, basename="product")
router.register("sales/invoices", SalesInvoiceViewSet, basename="salesinvoice")
router.register("sales/invoice-lines", SalesInvoiceLineViewSet, basename="salesinvoiceline")

urlpatterns = router.urls
