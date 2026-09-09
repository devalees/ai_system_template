"""
Data models for Multi-Tenancy, Organizations, and Workspaces.

Provides:
- Organization: Tenant entity with subscription tier, max seats, and metadata.
- OrganizationMembership: Junction associating users to organizations with RBAC roles.
- OrganizationInvitation: Expiring tokenized invitations for onboarded members.
"""

import secrets
from datetime import timedelta
from typing import Optional

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.models import UUIDModel, SoftDeleteModel, TimeStampedModel, AuditableModel


def default_invitation_expiry():
    """Return default expiration timestamp (7 days from now)."""
    return timezone.now() + timedelta(days=7)


class Organization(UUIDModel, SoftDeleteModel, AuditableModel):
    """
    Tenant representation for an isolated enterprise, company, or workspace.
    """
    TIER_FREE = "free"
    TIER_STARTER = "starter"
    TIER_PRO = "pro"
    TIER_ENTERPRISE = "enterprise"

    TIER_CHOICES = [
        (TIER_FREE, _("Free")),
        (TIER_STARTER, _("Starter")),
        (TIER_PRO, _("Pro")),
        (TIER_ENTERPRISE, _("Enterprise")),
    ]

    name = models.CharField(
        max_length=255,
        verbose_name=_("Organization Name"),
        help_text=_("Display name of the organization or workspace.")
    )
    slug = models.SlugField(
        max_length=100,
        unique=True,
        db_index=True,
        verbose_name=_("Slug"),
        help_text=_("Unique URL-friendly workspace identifier (e.g. 'acme-corp').")
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name=_("Is Active"),
        help_text=_("Indicates if this organization is active and operational.")
    )
    tier = models.CharField(
        max_length=32,
        choices=TIER_CHOICES,
        default=TIER_FREE,
        db_index=True,
        verbose_name=_("Subscription Tier"),
        help_text=_("Service tier determining feature limits and entitlements.")
    )
    max_users = models.PositiveIntegerField(
        default=10,
        verbose_name=_("Maximum Users"),
        help_text=_("Maximum number of seats permitted for this organization.")
    )
    domain = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        unique=True,
        verbose_name=_("Custom / Email Domain"),
        help_text=_("Optional custom domain or email domain mapped to this tenant.")
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Metadata"),
        help_text=_("Arbitrary workspace configuration and tenant preferences.")
    )

    class Meta:
        verbose_name = _("Organization")
        verbose_name_plural = _("Organizations")
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.slug})"

    @property
    def active_members_count(self) -> int:
        """Return the number of active members in this organization."""
        return self.memberships.filter(is_active=True).count()

    def can_add_user(self) -> bool:
        """Check if organization has available user seats."""
        return self.active_members_count < self.max_users

    def get_owner(self) -> Optional[settings.AUTH_USER_MODEL]:
        """Return the primary owner of the organization, if assigned."""
        owner_membership = self.memberships.filter(
            role=OrganizationMembership.ROLE_OWNER,
            is_active=True
        ).select_related("user").first()
        return owner_membership.user if owner_membership else None

    def is_member(self, user) -> bool:
        """Check if a given user is an active member of this organization."""
        if not user or not user.is_authenticated:
            return False
        return self.memberships.filter(user=user, is_active=True).exists()


class OrganizationMembership(UUIDModel, AuditableModel):
    """
    Role-based membership linking a User to an Organization.
    """
    ROLE_OWNER = "owner"
    ROLE_ADMIN = "admin"
    ROLE_MEMBER = "member"
    ROLE_VIEWER = "viewer"
    ROLE_GUEST = "guest"

    ROLE_CHOICES = [
        (ROLE_OWNER, _("Owner")),
        (ROLE_ADMIN, _("Admin")),
        (ROLE_MEMBER, _("Member")),
        (ROLE_VIEWER, _("Viewer")),
        (ROLE_GUEST, _("Guest")),
    ]

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="memberships",
        verbose_name=_("Organization"),
        help_text=_("The organization workspace.")
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="organization_memberships",
        verbose_name=_("User"),
        help_text=_("The member user.")
    )
    role = models.CharField(
        max_length=32,
        choices=ROLE_CHOICES,
        default=ROLE_MEMBER,
        db_index=True,
        verbose_name=_("Membership Role"),
        help_text=_("Role determining workspace permissions.")
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name=_("Is Active"),
        help_text=_("Designates whether this user membership is active.")
    )

    class Meta:
        verbose_name = _("Organization Membership")
        verbose_name_plural = _("Organization Memberships")
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "user"],
                name="unique_org_user_membership"
            )
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.user} - {self.organization.name} ({self.get_role_display()})"

    def clean(self):
        """Validate seat capacity when creating a new active membership."""
        super().clean()
        if self._state.adding and self.is_active:
            if not self.organization.can_add_user():
                raise ValidationError(
                    _("Organization seat limit reached (%(limit)d max users).")
                    % {"limit": self.organization.max_users}
                )


class OrganizationInvitation(UUIDModel, TimeStampedModel):
    """
    Expiring, tokenized invitation for inviting users to join an Organization.
    """
    STATUS_PENDING = "pending"
    STATUS_ACCEPTED = "accepted"
    STATUS_EXPIRED = "expired"
    STATUS_REVOKED = "revoked"

    STATUS_CHOICES = [
        (STATUS_PENDING, _("Pending")),
        (STATUS_ACCEPTED, _("Accepted")),
        (STATUS_EXPIRED, _("Expired")),
        (STATUS_REVOKED, _("Revoked")),
    ]

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="invitations",
        verbose_name=_("Organization"),
    )
    email = models.EmailField(
        db_index=True,
        verbose_name=_("Invited Email"),
        help_text=_("Email address of the invitee.")
    )
    role = models.CharField(
        max_length=32,
        choices=OrganizationMembership.ROLE_CHOICES,
        default=OrganizationMembership.ROLE_MEMBER,
        verbose_name=_("Role"),
        help_text=_("Role granted to the user upon accepting the invitation.")
    )
    token = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        default=secrets.token_urlsafe,
        verbose_name=_("Invitation Token"),
    )
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_org_invitations",
        verbose_name=_("Invited By"),
    )
    expires_at = models.DateTimeField(
        default=default_invitation_expiry,
        verbose_name=_("Expires At"),
    )
    accepted_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Accepted At"),
    )
    status = models.CharField(
        max_length=32,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
        verbose_name=_("Status"),
    )

    class Meta:
        verbose_name = _("Organization Invitation")
        verbose_name_plural = _("Organization Invitations")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Invite for {self.email} to {self.organization.name} [{self.status}]"

    @property
    def is_valid(self) -> bool:
        """Check if invitation is pending and not yet expired."""
        if self.status != self.STATUS_PENDING:
            return False
        return timezone.now() < self.expires_at

    def accept(self, user) -> OrganizationMembership:
        """
        Accept this invitation for a specific user, creating or updating membership.
        """
        if not self.is_valid:
            if self.status == self.STATUS_PENDING and timezone.now() >= self.expires_at:
                self.status = self.STATUS_EXPIRED
                self.save(update_fields=["status"])
            raise ValidationError(_("This invitation is no longer valid or has expired."))

        with transaction.atomic():
            membership, created = OrganizationMembership.objects.get_or_create(
                organization=self.organization,
                user=user,
                defaults={"role": self.role, "is_active": True}
            )
            if not created and not membership.is_active:
                membership.is_active = True
                membership.role = self.role
                membership.save(update_fields=["is_active", "role"])

            self.status = self.STATUS_ACCEPTED
            self.accepted_at = timezone.now()
            self.save(update_fields=["status", "accepted_at"])

            return membership

    def revoke(self):
        """Revoke a pending invitation."""
        if self.status == self.STATUS_PENDING:
            self.status = self.STATUS_REVOKED
            self.save(update_fields=["status"])
