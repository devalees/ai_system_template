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
