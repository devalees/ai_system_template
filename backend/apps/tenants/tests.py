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

