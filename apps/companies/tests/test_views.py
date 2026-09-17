import pytest
from django.test import Client
from django.urls import reverse

from apps.companies.models import MembershipRole
from apps.companies.tests.factories import CompanyFactory, CompanyMembershipFactory, UserFactory

pytestmark = pytest.mark.django_db


def test_login_page_renders():
    response = Client().get(reverse("login"))

    assert response.status_code == 200


def test_switch_page_lists_active_memberships():
    user = UserFactory()
    company = CompanyFactory()
    CompanyMembershipFactory(user=user, company=company, role=MembershipRole.OWNER)
    client = Client()
    client.force_login(user)

    response = client.get(reverse("companies:switch"))

    assert response.status_code == 200
    assert company in [m.company for m in response.context["memberships"]]


def test_switch_view_activates_owned_company():
    user = UserFactory()
    company = CompanyFactory()
    CompanyMembershipFactory(user=user, company=company, role=MembershipRole.OWNER)
    client = Client()
    client.force_login(user)

    response = client.post(reverse("companies:switch"), {"company_id": company.id})

    assert response.status_code == 302
    assert client.session["active_company_id"] == company.id


def test_switch_view_rejects_foreign_company():
    user = UserFactory()
    foreign_company = CompanyFactory()
    client = Client()
    client.force_login(user)

    response = client.post(reverse("companies:switch"), {"company_id": foreign_company.id})

    assert response.status_code == 302
    assert "active_company_id" not in client.session


def test_switch_view_rejects_inactive_company():
    user = UserFactory()
    company = CompanyFactory(is_active=False)
    CompanyMembershipFactory(user=user, company=company, role=MembershipRole.OWNER)
    client = Client()
    client.force_login(user)

    response = client.post(reverse("companies:switch"), {"company_id": company.id})

    assert response.status_code == 302
    assert "active_company_id" not in client.session


def test_switch_view_rejects_non_numeric_company_id_without_500():
    user = UserFactory()
    client = Client()
    client.force_login(user)

    response = client.post(reverse("companies:switch"), {"company_id": "not-an-id"})

    assert response.status_code == 302
    assert "active_company_id" not in client.session


def test_switch_view_ignores_unsafe_next_and_falls_back_to_default():
    user = UserFactory()
    company = CompanyFactory()
    CompanyMembershipFactory(user=user, company=company, role=MembershipRole.OWNER)
    client = Client()
    client.force_login(user)

    response = client.post(
        reverse("companies:switch"),
        {"company_id": company.id, "next": "https://evil.example.com/phish"},
    )

    assert response.status_code == 302
    assert response.url == reverse("partners:list")


def test_switch_view_follows_safe_relative_next():
    user = UserFactory()
    company = CompanyFactory()
    CompanyMembershipFactory(user=user, company=company, role=MembershipRole.OWNER)
    client = Client()
    client.force_login(user)

    response = client.post(
        reverse("companies:switch"),
        {"company_id": company.id, "next": reverse("catalog:list")},
    )

    assert response.status_code == 302
    assert response.url == reverse("catalog:list")


def test_switch_requires_authentication():
    client = Client()

    response = client.post(reverse("companies:switch"), {"company_id": "1"})

    assert response.status_code == 302
    assert response.url.startswith(reverse("login"))


def test_switch_requires_post_to_mutate_session():
    user = UserFactory()
    company = CompanyFactory()
    CompanyMembershipFactory(user=user, company=company, role=MembershipRole.OWNER)
    client = Client()
    client.force_login(user)

    response = client.get(reverse("companies:switch") + f"?company_id={company.id}")

    assert response.status_code == 200
    assert "active_company_id" not in client.session
