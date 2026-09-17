from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path(
        "accounts/login/",
        auth_views.LoginView.as_view(template_name="registration/login.html"),
        name="login",
    ),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("companies/", include("apps.companies.urls")),
    path("partners/", include("apps.partners.urls")),
    path("catalog/", include("apps.catalog.urls")),
    path("sales/", include("apps.sales.urls")),
    path("api/v1/", include("config.api_urls")),
]
