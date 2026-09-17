from django.urls import path

from apps.sales.views import (
    SalesInvoiceCreateView,
    SalesInvoiceDetailView,
    SalesInvoiceIssueView,
    SalesInvoiceLineAddView,
    SalesInvoiceLineDeleteView,
    SalesInvoiceLineEditView,
    SalesInvoiceListView,
    SalesInvoiceUpdateView,
    SalesInvoiceVoidView,
)

app_name = "sales"

urlpatterns = [
    path("", SalesInvoiceListView.as_view(), name="list"),
    path("new/", SalesInvoiceCreateView.as_view(), name="create"),
    path("<int:pk>/", SalesInvoiceDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", SalesInvoiceUpdateView.as_view(), name="edit"),
    path("<int:pk>/lines/add/", SalesInvoiceLineAddView.as_view(), name="line-add"),
    path(
        "<int:pk>/lines/<int:line_pk>/edit/",
        SalesInvoiceLineEditView.as_view(),
        name="line-edit",
    ),
    path(
        "<int:pk>/lines/<int:line_pk>/delete/",
        SalesInvoiceLineDeleteView.as_view(),
        name="line-delete",
    ),
    path("<int:pk>/issue/", SalesInvoiceIssueView.as_view(), name="issue"),
    path("<int:pk>/void/", SalesInvoiceVoidView.as_view(), name="void"),
]
