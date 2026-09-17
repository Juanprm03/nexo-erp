from django.urls import path

from apps.partners.views import (
    PartnerCreateView,
    PartnerDeactivateView,
    PartnerDetailView,
    PartnerListView,
    PartnerUpdateView,
)

app_name = "partners"

urlpatterns = [
    path("", PartnerListView.as_view(), name="list"),
    path("new/", PartnerCreateView.as_view(), name="create"),
    path("<int:pk>/", PartnerDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", PartnerUpdateView.as_view(), name="edit"),
    path("<int:pk>/deactivate/", PartnerDeactivateView.as_view(), name="deactivate"),
]
