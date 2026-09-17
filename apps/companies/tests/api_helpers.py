"""Shared test helper for exercising company scoping through the DRF API
from other apps' test suites (partners, catalog, ...).

IMPORTANT: use `force_login`, never DRF's `force_authenticate`.
`ActiveCompanyMiddleware` is plain Django middleware that reads the real
`request.user` set by `AuthenticationMiddleware` from an actual session.
`APIClient.force_authenticate()` does NOT set that — it only patches DRF's
lazy `Request.user` property inside the view layer, after our middleware
has already run. Using it here would make `request.active_company`
resolve to None on every request, silently breaking every scoped test.
"""

from rest_framework.test import APIClient

from apps.companies.services import ACTIVE_COMPANY_SESSION_KEY


def api_client_for(user, company=None):
    client = APIClient()
    client.force_login(user)
    if company is not None:
        session = client.session
        session[ACTIVE_COMPANY_SESSION_KEY] = company.id
        session.save()
    return client
