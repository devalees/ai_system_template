"""
Automated tests for Multi-Tenancy models, memberships, and invitations.
"""

from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from apps.tenants.models import (
    Organization,
    OrganizationMembership,
    OrganizationInvitation,
)

User = get_user_model()


class OrganizationModelTests(TestCase):
    """Verify Organization lifecycle, constraints, and helpers."""

    def setUp(self):
        self.user = User.objects.create_user(username="tenant_owner", password="password123")

    def test_organization_creation_and_str(self):
        org = Organization.objects.create(
            name="Acme Corporation",
            slug="acme-corp",
            tier=Organization.TIER_PRO,
            max_users=25
        )
        self.assertEqual(str(org), "Acme Corporation (acme-corp)")
        self.assertTrue(org.is_active)
        self.assertEqual(org.tier, "pro")
        self.assertEqual(org.max_users, 25)

    def test_organization_slug_uniqueness(self):
        Organization.objects.create(name="Org One", slug="shared-slug")
        with self.assertRaises(IntegrityError):
            Organization.objects.create(name="Org Two", slug="shared-slug")

    def test_active_members_count_and_seat_limits(self):
        org = Organization.objects.create(name="Small Team", slug="small-team", max_users=2)
        u1 = User.objects.create_user(username="u1", password="pw")
        u2 = User.objects.create_user(username="u2", password="pw")
        u3 = User.objects.create_user(username="u3", password="pw")

        OrganizationMembership.objects.create(organization=org, user=u1, role="owner")
        self.assertEqual(org.active_members_count, 1)
        self.assertTrue(org.can_add_user())

        OrganizationMembership.objects.create(organization=org, user=u2, role="member")
        self.assertEqual(org.active_members_count, 2)
        self.assertFalse(org.can_add_user())

        # Exceeding limit via clean() should raise ValidationError
        m3 = OrganizationMembership(organization=org, user=u3, role="member")
        with self.assertRaises(ValidationError):
            m3.clean()

    def test_organization_is_member_and_get_owner(self):
        org = Organization.objects.create(name="Tech Labs", slug="tech-labs")
        OrganizationMembership.objects.create(
            organization=org,
            user=self.user,
            role=OrganizationMembership.ROLE_OWNER
        )

        self.assertTrue(org.is_member(self.user))
        self.assertEqual(org.get_owner(), self.user)

        stranger = User.objects.create_user(username="stranger", password="pw")
        self.assertFalse(org.is_member(stranger))


class OrganizationMembershipTests(TestCase):
    """Verify membership constraints, roles, and cascade behavior."""

    def setUp(self):
        self.org = Organization.objects.create(name="Nexus", slug="nexus")
        self.user = User.objects.create_user(username="nexus_user", password="pw")

    def test_membership_unique_constraint(self):
        OrganizationMembership.objects.create(
            organization=self.org,
            user=self.user,
            role=OrganizationMembership.ROLE_ADMIN
        )
        with self.assertRaises(IntegrityError):
            OrganizationMembership.objects.create(
                organization=self.org,
                user=self.user,
                role=OrganizationMembership.ROLE_MEMBER
            )

    def test_membership_str_representation(self):
        m = OrganizationMembership.objects.create(
            organization=self.org,
            user=self.user,
            role=OrganizationMembership.ROLE_OWNER
        )
        self.assertIn("nexus_user", str(m))
        self.assertIn("Nexus", str(m))


class OrganizationInvitationTests(TestCase):
    """Verify invitation creation, expiration, and acceptance flow."""

    def setUp(self):
        self.org = Organization.objects.create(name="Cloud Corp", slug="cloud-corp")
        self.inviter = User.objects.create_user(username="inviter", password="pw")
        self.invitee = User.objects.create_user(username="invitee", email="invitee@example.com", password="pw")

    def test_invitation_lifecycle_and_acceptance(self):
        invite = OrganizationInvitation.objects.create(
            organization=self.org,
            email="invitee@example.com",
            role=OrganizationMembership.ROLE_ADMIN,
            invited_by=self.inviter
        )
        self.assertTrue(invite.is_valid)
        self.assertEqual(invite.status, OrganizationInvitation.STATUS_PENDING)

        # Accept invitation
        membership = invite.accept(self.invitee)
        self.assertEqual(membership.organization, self.org)
        self.assertEqual(membership.user, self.invitee)
        self.assertEqual(membership.role, OrganizationMembership.ROLE_ADMIN)
        self.assertTrue(membership.is_active)

        invite.refresh_from_db()
        self.assertEqual(invite.status, OrganizationInvitation.STATUS_ACCEPTED)
        self.assertIsNotNone(invite.accepted_at)
        self.assertFalse(invite.is_valid)

        # Attempting to accept again should fail
        with self.assertRaises(ValidationError):
            invite.accept(self.invitee)

    def test_expired_invitation_cannot_be_accepted(self):
        invite = OrganizationInvitation.objects.create(
            organization=self.org,
            email="late@example.com",
            role=OrganizationMembership.ROLE_MEMBER,
            invited_by=self.inviter,
            expires_at=timezone.now() - timedelta(hours=1)
        )
        self.assertFalse(invite.is_valid)
        with self.assertRaises(ValidationError):
            invite.accept(self.invitee)

        invite.refresh_from_db()
        self.assertEqual(invite.status, OrganizationInvitation.STATUS_EXPIRED)

    def test_revoked_invitation_cannot_be_accepted(self):
        invite = OrganizationInvitation.objects.create(
            organization=self.org,
            email="revoked@example.com",
            role=OrganizationMembership.ROLE_MEMBER,
            invited_by=self.inviter
        )
        invite.revoke()
        self.assertEqual(invite.status, OrganizationInvitation.STATUS_REVOKED)
        self.assertFalse(invite.is_valid)

        with self.assertRaises(ValidationError):
            invite.accept(self.invitee)


class TenantContextTests(TestCase):
    """Verify thread-safe contextvars tenant management and bypasses."""

    def setUp(self):
        self.org = Organization.objects.create(name="Alpha Org", slug="alpha-org")

    def test_tenant_context_scoping(self):
        from apps.tenants.context import get_current_tenant, tenant_context
        self.assertIsNone(get_current_tenant())

        with tenant_context(self.org):
            self.assertEqual(get_current_tenant(), self.org)

        self.assertIsNone(get_current_tenant())

    def test_bypass_tenant_isolation(self):
        from apps.tenants.context import is_tenant_isolation_bypassed, bypass_tenant_isolation
        self.assertFalse(is_tenant_isolation_bypassed())

        with bypass_tenant_isolation():
            self.assertTrue(is_tenant_isolation_bypassed())

        self.assertFalse(is_tenant_isolation_bypassed())


class TenantMiddlewareTests(TestCase):
    """Verify middleware resolution strategies and security gates."""

    def setUp(self):
        from django.test import RequestFactory
        from apps.tenants.middleware import TenantMiddleware

        self.factory = RequestFactory()
        self.middleware = TenantMiddleware(get_response=lambda r: r)
        self.org1 = Organization.objects.create(name="Org One", slug="org-one")
        self.org2 = Organization.objects.create(name="Org Two", slug="org-two")

        self.user1 = User.objects.create_user(username="user1", password="pw")
        OrganizationMembership.objects.create(organization=self.org1, user=self.user1, role="member")

        self.superuser = User.objects.create_superuser(username="admin_user", email="admin@test.com", password="pw")

    def test_resolve_via_header_slug(self):
        from apps.tenants.context import get_current_tenant

        request = self.factory.get("/", HTTP_X_WORKSPACE_SLUG="org-one")
        request.user = self.user1

        self.middleware(request)
        self.assertEqual(request.tenant, self.org1)
        self.assertEqual(request.organization, self.org1)
        # Verify context is cleaned up after request
        self.assertIsNone(get_current_tenant())

    def test_resolve_via_header_uuid(self):
        request = self.factory.get("/", HTTP_X_ORGANIZATION_ID=str(self.org1.id))
        request.user = self.user1

        self.middleware(request)
        self.assertEqual(request.tenant, self.org1)

    def test_resolve_via_query_param(self):
        request = self.factory.get("/?workspace=org-one")
        request.user = self.user1

        self.middleware(request)
        self.assertEqual(request.tenant, self.org1)

    def test_resolve_via_user_default_membership(self):
        request = self.factory.get("/")
        request.user = self.user1

        self.middleware(request)
        self.assertEqual(request.tenant, self.org1)

    def test_explicit_workspace_forbidden_for_non_members(self):
        # User 1 is a member of Org 1, but requests Org 2
        request = self.factory.get("/", HTTP_X_WORKSPACE_SLUG="org-two")
        request.user = self.user1

        response = self.middleware(request)
        self.assertEqual(response.status_code, 403)

    def test_superuser_can_access_any_explicit_workspace(self):
        request = self.factory.get("/", HTTP_X_WORKSPACE_SLUG="org-two")
        request.user = self.superuser

        response = self.middleware(request)
        self.assertEqual(request.tenant, self.org2)
        # Response should pass through without 403
        self.assertEqual(response, request)


from django.db import connection, models
from apps.core.models import UUIDModel, SoftDeleteModel
from apps.tenants.base_models import TenantAwareModel
from apps.tenants.context import tenant_context, bypass_tenant_isolation


class ConcreteTenantItem(UUIDModel, TenantAwareModel, SoftDeleteModel):
    """Concrete model created specifically to verify TenantAwareModel."""
    title = models.CharField(max_length=100)

    class Meta:
        app_label = "tenants"


class TenantAwareModelTests(TestCase):
    """Verify row-level tenant isolation, auto-population, and soft delete."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with connection.schema_editor() as editor:
            editor.create_model(ConcreteTenantItem)

    @classmethod
    def tearDownClass(cls):
        with connection.schema_editor() as editor:
            editor.delete_model(ConcreteTenantItem)
        super().tearDownClass()

    def setUp(self):
        self.org_a = Organization.objects.create(name="Org A", slug="org-a")
        self.org_b = Organization.objects.create(name="Org B", slug="org-b")

    def test_auto_populate_organization_from_context(self):
        with tenant_context(self.org_a):
            item = ConcreteTenantItem.objects.create(title="Document A")
            self.assertEqual(item.organization, self.org_a)

    def test_row_level_tenant_query_scoping(self):
        with tenant_context(self.org_a):
            ConcreteTenantItem.objects.create(title="Alpha Doc")

        with tenant_context(self.org_b):
            ConcreteTenantItem.objects.create(title="Beta Doc")

        # In Org A context, only Alpha Doc should be visible
        with tenant_context(self.org_a):
            items_a = ConcreteTenantItem.objects.all()
            self.assertEqual(items_a.count(), 1)
            self.assertEqual(items_a.first().title, "Alpha Doc")

        # In Org B context, only Beta Doc should be visible
        with tenant_context(self.org_b):
            items_b = ConcreteTenantItem.objects.all()
            self.assertEqual(items_b.count(), 1)
            self.assertEqual(items_b.first().title, "Beta Doc")

    def test_soft_delete_with_tenant_manager(self):
        with tenant_context(self.org_a):
            item = ConcreteTenantItem.objects.create(title="Trashable")
            self.assertEqual(ConcreteTenantItem.objects.count(), 1)

            # Soft delete
            item.delete()
            self.assertEqual(ConcreteTenantItem.objects.count(), 0)

            # Unfiltered all_objects still contains it
            self.assertEqual(ConcreteTenantItem.all_objects.count(), 1)

    def test_bypass_tenant_isolation_shows_all_records(self):
        with tenant_context(self.org_a):
            ConcreteTenantItem.objects.create(title="Global 1")

        with tenant_context(self.org_b):
            ConcreteTenantItem.objects.create(title="Global 2")

        with bypass_tenant_isolation():
            self.assertEqual(ConcreteTenantItem.objects.count(), 2)


class DynamicModelTenantTests(TestCase):
    """Verify that dynamic models compiled via MetaEngine support full multi-tenancy."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from apps.meta_engine.models import MetaModel, MetaField
        from apps.meta_engine.schema_engine import DynamicSchemaEngine
        from apps.meta_engine.model_factory import DynamicModelFactory

        cls.meta_model = MetaModel.objects.create(
            name="tenant_task",
            label="Tenant Task",
            app_label="tenants_test",
            table_name="app_test_tenant_task",
            is_tenant_aware=True,
            is_soft_delete=True,
            is_auditable=True,
        )
        MetaField.objects.create(
            model=cls.meta_model,
            name="title",
            field_type="char",
            label="Title",
        )
        DynamicSchemaEngine.create_table(cls.meta_model)
        cls.dynamic_cls = DynamicModelFactory.get_or_create_model(cls.meta_model, force_reload=True)

    @classmethod
    def tearDownClass(cls):
        from apps.meta_engine.schema_engine import DynamicSchemaEngine
        DynamicSchemaEngine.drop_table(cls.meta_model)
        cls.meta_model.delete()
        super().tearDownClass()

    def setUp(self):
        self.org_x = Organization.objects.create(name="Org X", slug="org-x")
        self.org_y = Organization.objects.create(name="Org Y", slug="org-y")

    def test_dynamic_model_inherits_tenant_aware_model(self):
        from apps.tenants.base_models import TenantAwareModel
        self.assertTrue(issubclass(self.dynamic_cls, TenantAwareModel))
        # Verify organization field is present on dynamic model
        field_names = [f.name for f in self.dynamic_cls._meta.fields]
        self.assertIn("organization", field_names)

    def test_dynamic_model_row_level_isolation(self):
        with tenant_context(self.org_x):
            self.dynamic_cls.objects.create(title="Task for Org X")

        with tenant_context(self.org_y):
            self.dynamic_cls.objects.create(title="Task for Org Y")

        with tenant_context(self.org_x):
            tasks_x = self.dynamic_cls.objects.all()
            self.assertEqual(tasks_x.count(), 1)
            self.assertEqual(tasks_x.first().title, "Task for Org X")

        with tenant_context(self.org_y):
            tasks_y = self.dynamic_cls.objects.all()
            self.assertEqual(tasks_y.count(), 1)
            self.assertEqual(tasks_y.first().title, "Task for Org Y")



