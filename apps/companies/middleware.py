from apps.companies.models import CompanyMembership
from apps.companies.services import ACTIVE_COMPANY_SESSION_KEY


class ActiveCompanyMiddleware:
    """Resolves `request.active_company` from the session on every request.

    Re-validates the membership (and the company itself) on every request
    instead of trusting the session id blindly — if a membership is
    deactivated or the company is deactivated mid-session, access is lost
    on the very next request, not just at the next login.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.active_company = self._resolve(request)
        return self.get_response(request)

    def _resolve(self, request):
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return None

        company_id = request.session.get(ACTIVE_COMPANY_SESSION_KEY)
        if not company_id:
            return None

        membership = (
            CompanyMembership.objects.filter(user=user, company_id=company_id, is_active=True)
            .select_related("company")
            .first()
        )
        if membership is None or not membership.company.is_active:
            request.session.pop(ACTIVE_COMPANY_SESSION_KEY, None)
            return None

        return membership.company
