import factory
from factory.django import DjangoModelFactory

from apps.accounts.models import User
from apps.companies.models import Company, CompanyMembership, MembershipRole


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User
        skip_postgeneration_save = True

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    first_name = "Test"
    last_name = "User"

    @factory.post_generation
    def password(self, create, extracted, **kwargs):
        self.set_password(extracted or "testpass123")
        if create:
            self.save()


class CompanyFactory(DjangoModelFactory):
    class Meta:
        model = Company

    name = factory.Sequence(lambda n: f"Company {n}")
    tax_id = factory.Sequence(lambda n: f"NIT-{n}")


class CompanyMembershipFactory(DjangoModelFactory):
    class Meta:
        model = CompanyMembership

    user = factory.SubFactory(UserFactory)
    company = factory.SubFactory(CompanyFactory)
    role = MembershipRole.READONLY
    is_active = True
