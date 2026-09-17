from django.urls import path

from apps.companies.views import CompanySwitchView

app_name = "companies"

urlpatterns = [
    path("switch/", CompanySwitchView.as_view(), name="switch"),
]
