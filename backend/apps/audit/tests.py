"""
Tests for Comprehensive Activity Audit Trail (apps.audit).
"""

import uuid
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from apps.audit.models import ActivityLog, ImmutabilityError
from apps.tenants.models import Organization

User = get_user_model()


class ActivityLogModelTests(TestCase):
    """
    Test suite for ActivityLog immutability, GFK targets, and data persistence.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="audittestuser",
            email="audit@example.com",
            password="securepassword123",
        )
        self.org = Organization.objects.create(
            name="Audit Corp",
            slug="audit-corp",
            created_by=self.user,
        )

    def test_create_activity_log_with_tenant_and_actor(self):
        """Verify normal creation of an audit log entry."""
        ct = ContentType.objects.get_for_model(self.org)
        log = ActivityLog.objects.create(
            organization=self.org,
            actor=self.user,
            actor_type=ActivityLog.ACTOR_USER,
            action=ActivityLog.ACTION_CREATE,
            status=ActivityLog.STATUS_SUCCESS,
            content_type=ct,
            object_id=str(self.org.id),
            object_repr=self.org.name,
            changes={"name": {"old": None, "new": "Audit Corp"}},
            ip_address="192.168.1.100",
            user_agent="Mozilla/5.0 TestBrowser",
            request_id="req-12345",
            metadata={"source": "api_call"},
        )

        self.assertIsNotNone(log.id)
        self.assertEqual(log.content_object, self.org)
        self.assertEqual(log.organization, self.org)
        self.assertEqual(log.actor, self.user)
        self.assertIn("audittestuser", str(log))
        self.assertIn("Create", str(log))

    def test_create_system_level_activity_log_without_org(self):
        """Verify global system actions can be recorded without organization."""
        log = ActivityLog.objects.create(
            actor_type=ActivityLog.ACTOR_SYSTEM,
            action=ActivityLog.ACTION_CUSTOM,
            status=ActivityLog.STATUS_SUCCESS,
            object_repr="System Scheduler",
            metadata={"job": "cleanup_cache"},
        )
        self.assertIsNone(log.organization)
        self.assertIsNone(log.actor)
        self.assertIn("System / Background Process", str(log))

    def test_generic_foreign_key_with_integer_pk_model(self):
        """Verify GFK functions with integer PK models (e.g. auth.User)."""
        ct = ContentType.objects.get_for_model(self.user)
        log = ActivityLog.objects.create(
            actor_type=ActivityLog.ACTOR_SYSTEM,
            action=ActivityLog.ACTION_LOGIN,
            content_type=ct,
            object_id=str(self.user.pk),
            object_repr=self.user.username,
        )
        self.assertEqual(log.content_object, self.user)

    def test_immutability_enforced_on_save(self):
        """Verify attempting to update an existing ActivityLog raises ImmutabilityError."""
        log = ActivityLog.objects.create(
            actor=self.user,
            action=ActivityLog.ACTION_CREATE,
            object_repr="Test Target",
        )

        log.object_repr = "Modified Target"
        with self.assertRaises(ImmutabilityError):
            log.save()

        # Reload from DB and verify value was not changed
        log.refresh_from_db()
        self.assertEqual(log.object_repr, "Test Target")

    def test_immutability_enforced_on_delete_without_purge_flag(self):
        """Verify delete() raises ImmutabilityError unless allow_purge=True is provided."""
        log = ActivityLog.objects.create(
            actor=self.user,
            action=ActivityLog.ACTION_DELETE,
            object_repr="Deleted Item",
        )

        with self.assertRaises(ImmutabilityError):
            log.delete()

        self.assertTrue(ActivityLog.objects.filter(pk=log.pk).exists())

        # Calling delete with allow_purge=True should succeed
        log.delete(allow_purge=True)
        self.assertFalse(ActivityLog.objects.filter(pk=log.pk).exists())
