from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from apps.catalog.forms import ProductForm
from apps.catalog.models import Product
from apps.companies.mixins import (
    CompanyRoleRequiredMixin,
    CompanyScopedFormMixin,
    CompanyScopedQuerysetMixin,
)
from apps.companies.models import MANAGEMENT_ROLES, MembershipRole

VIEW_ROLES = tuple(MembershipRole.values)
WRITE_ROLES = MANAGEMENT_ROLES


class ProductListView(CompanyRoleRequiredMixin, CompanyScopedQuerysetMixin, ListView):
    allowed_roles = VIEW_ROLES
    model = Product
    paginate_by = 25
    template_name = "catalog/product_list.html"
    context_object_name = "products"


class ProductDetailView(CompanyRoleRequiredMixin, CompanyScopedQuerysetMixin, DetailView):
    allowed_roles = VIEW_ROLES
    model = Product
    template_name = "catalog/product_detail.html"
    context_object_name = "product"


class ProductCreateView(CompanyRoleRequiredMixin, CompanyScopedFormMixin, CreateView):
    allowed_roles = WRITE_ROLES
    model = Product
    form_class = ProductForm
    template_name = "catalog/product_form.html"
    success_url = reverse_lazy("catalog:list")

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Producto creado correctamente.")
        return response


class ProductUpdateView(CompanyRoleRequiredMixin, CompanyScopedFormMixin, UpdateView):
    allowed_roles = WRITE_ROLES
    model = Product
    form_class = ProductForm
    template_name = "catalog/product_form.html"
    success_url = reverse_lazy("catalog:list")

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Producto actualizado correctamente.")
        return response


class ProductDeactivateView(CompanyRoleRequiredMixin, View):
    allowed_roles = WRITE_ROLES

    def post(self, request, pk):
        product = get_object_or_404(
            Product.objects.for_company(request.active_company), pk=pk
        )
        product.is_active = False
        product.save(update_fields=["is_active", "updated_at"])
        messages.success(request, f"{product.name} desactivado.")
        return redirect("catalog:list")
