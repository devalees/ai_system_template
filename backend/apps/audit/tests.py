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

    def test_bulk_immutability_enforced_on_queryset(self):
        """Verify QuerySet.update and QuerySet.delete enforce immutability."""
        log = ActivityLog.objects.create(
            actor=self.user,
            action=ActivityLog.ACTION_CREATE,
            object_repr="Bulk Item",
        )

        with self.assertRaises(ImmutabilityError):
            ActivityLog.objects.filter(pk=log.pk).update(object_repr="Illegal Update")

        with self.assertRaises(ImmutabilityError):
            ActivityLog.objects.filter(pk=log.pk).delete()

        # QuerySet delete with allow_purge=True should succeed
        ActivityLog.objects.filter(pk=log.pk).delete(allow_purge=True)
        self.assertFalse(ActivityLog.objects.filter(pk=log.pk).exists())


class AuditContextAndMiddlewareTests(TestCase):
    """
    Test suite for audit contextvars and AuditContextMiddleware telemetry extraction.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="telemetryuser",
            email="telemetry@example.com",
            password="testpassword123",
        )

    def test_audit_context_manager(self):
        """Verify audit_context sets and cleans up context variables."""
        from apps.audit.context import (
            audit_context,
            get_audit_ip,
            get_audit_user_agent,
            get_audit_request_id,
            get_audit_actor,
            get_audit_metadata,
        )

        self.assertIsNone(get_audit_ip())
        self.assertEqual(get_audit_user_agent(), "")
        self.assertEqual(get_audit_request_id(), "")
        self.assertIsNone(get_audit_actor())
        self.assertEqual(get_audit_metadata(), {})

        with audit_context(
            actor=self.user,
            ip="203.0.113.195",
            user_agent="CustomTestAgent/1.0",
            request_id="req-test-999",
            metadata={"source": "unit_test"},
        ):
            self.assertEqual(get_audit_ip(), "203.0.113.195")
            self.assertEqual(get_audit_user_agent(), "CustomTestAgent/1.0")
            self.assertEqual(get_audit_request_id(), "req-test-999")
            self.assertEqual(get_audit_actor(), self.user)
            self.assertEqual(get_audit_metadata(), {"source": "unit_test"})

        # Verify context is cleaned up after exiting context manager
        self.assertIsNone(get_audit_ip())
        self.assertEqual(get_audit_user_agent(), "")
        self.assertEqual(get_audit_request_id(), "")
        self.assertIsNone(get_audit_actor())
        self.assertEqual(get_audit_metadata(), {})

    def test_middleware_telemetry_extraction(self):
        """Verify middleware extracts IP, user agent, correlation ID and resets context."""
        from django.test import RequestFactory
        from django.http import HttpResponse
        from apps.audit.middleware import AuditContextMiddleware
        from apps.audit.context import (
            get_audit_ip,
            get_audit_user_agent,
            get_audit_request_id,
            get_audit_actor,
        )

        factory = RequestFactory()
        request = factory.get(
            "/api/test/",
            HTTP_X_FORWARDED_FOR="198.51.100.42, 10.0.0.1",
            HTTP_USER_AGENT="PyTest/7.0",
            HTTP_X_REQUEST_ID="custom-req-id-777",
        )
        request.user = self.user

        context_observed = {}

        def sample_view(req):
            context_observed["ip"] = get_audit_ip()
            context_observed["ua"] = get_audit_user_agent()
            context_observed["req_id"] = get_audit_request_id()
            context_observed["actor"] = get_audit_actor()
            return HttpResponse("OK")

        middleware = AuditContextMiddleware(sample_view)
        response = middleware(request)

        # Verify values captured inside view execution
        self.assertEqual(context_observed["ip"], "198.51.100.42")
        self.assertEqual(context_observed["ua"], "PyTest/7.0")
        self.assertEqual(context_observed["req_id"], "custom-req-id-777")
        self.assertEqual(context_observed["actor"], self.user)

        # Verify response header
        self.assertEqual(response["X-Request-ID"], "custom-req-id-777")

        # Verify context is reset after middleware completes
        self.assertIsNone(get_audit_ip())
        self.assertEqual(get_audit_user_agent(), "")
        self.assertEqual(get_audit_request_id(), "")
        self.assertIsNone(get_audit_actor())

    def test_middleware_generates_request_id_when_missing(self):
        """Verify middleware creates a unique request ID if header is absent."""
        from django.test import RequestFactory
        from django.http import HttpResponse
        from apps.audit.middleware import AuditContextMiddleware

        factory = RequestFactory()
        request = factory.get("/api/test/")
        request.user = None

        middleware = AuditContextMiddleware(lambda req: HttpResponse("OK"))
        response = middleware(request)

        self.assertTrue(response.has_header("X-Request-ID"))
        self.assertTrue(response["X-Request-ID"].startswith("req_"))


class AuditSignalAndDiffingTests(TestCase):
    """
    Test suite for model diffing signals and security authentication events.
    """

    def setUp(self):
        from apps.audit.registry import register_auditable
        register_auditable(Organization)

        self.user = User.objects.create_user(
            username="signalsuser",
            email="signals@example.com",
            password="securePassword456!",
        )

    def tearDown(self):
        from apps.audit.registry import unregister_auditable
        unregister_auditable(Organization)

    def test_model_create_signal_generates_audit_log(self):
        """Verify saving a new auditable model creates an ActivityLog with CREATE action."""
        from apps.audit.context import audit_context

        with audit_context(
            actor=self.user,
            ip="10.20.30.40",
            user_agent="SignalTester/1.0",
            request_id="req-sig-001",
        ):
            org = Organization.objects.create(
                name="Acme Signals",
                slug="acme-signals",
                created_by=self.user,
            )

        log = ActivityLog.objects.filter(
            object_id=str(org.id),
            action=ActivityLog.ACTION_CREATE,
        ).first()

        self.assertIsNotNone(log)
        self.assertEqual(log.actor, self.user)
        self.assertEqual(log.ip_address, "10.20.30.40")
        self.assertEqual(log.user_agent, "SignalTester/1.0")
        self.assertEqual(log.request_id, "req-sig-001")
        self.assertIn("name", log.changes)
        self.assertEqual(log.changes["name"]["new"], "Acme Signals")

    def test_model_update_signal_generates_diff(self):
        """Verify modifying fields generates an ActivityLog with old/new diff."""
        from apps.audit.context import audit_context

        org = Organization.objects.create(
            name="Initial Name",
            slug="initial-slug",
            created_by=self.user,
        )
        # Clear creation log
        ActivityLog.objects.filter(object_id=str(org.id)).delete(allow_purge=True)

        with audit_context(actor=self.user, request_id="req-update-123"):
            org.name = "Updated Name"
            org.max_users = 50
            org.save()

        log = ActivityLog.objects.filter(
            object_id=str(org.id),
            action=ActivityLog.ACTION_UPDATE,
        ).first()

        self.assertIsNotNone(log)
        self.assertEqual(log.changes["name"]["old"], "Initial Name")
        self.assertEqual(log.changes["name"]["new"], "Updated Name")
        self.assertEqual(log.changes["max_users"]["old"], 10)
        self.assertEqual(log.changes["max_users"]["new"], 50)
        # Ensure updated_at is NOT in changes diff
        self.assertNotIn("updated_at", log.changes)

    def test_model_update_without_changes_skips_audit_log(self):
        """Verify saving without changing fields suppresses empty audit logs."""
        from apps.audit.context import audit_context

        org = Organization.objects.create(
            name="Static Org",
            slug="static-org",
            created_by=self.user,
        )
        ActivityLog.objects.filter(object_id=str(org.id)).delete(allow_purge=True)

        with audit_context(actor=self.user):
            org.save()

        count = ActivityLog.objects.filter(object_id=str(org.id)).count()
        self.assertEqual(count, 0)

    def test_model_soft_delete_and_restore_signals(self):
        """Verify soft-deleting and restoring an auditable model creates DELETE and RESTORE audit logs."""
        from apps.audit.context import audit_context

        org = Organization.objects.create(
            name="Soft Delete Org",
            slug="soft-delete-org",
            created_by=self.user,
        )
        org_id = str(org.id)

        # 1. Soft delete
        with audit_context(actor=self.user, request_id="req-soft-del"):
            org.delete()  # Performs soft delete (is_deleted=True)

        soft_del_log = ActivityLog.objects.filter(
            object_id=org_id,
            action=ActivityLog.ACTION_DELETE,
        ).first()
        self.assertIsNotNone(soft_del_log)
        self.assertEqual(soft_del_log.changes["is_deleted"]["old"], False)
        self.assertEqual(soft_del_log.changes["is_deleted"]["new"], True)

        # 2. Restore
        with audit_context(actor=self.user, request_id="req-restore"):
            org.restore()

        restore_log = ActivityLog.objects.filter(
            object_id=org_id,
            action=ActivityLog.ACTION_RESTORE,
        ).first()
        self.assertIsNotNone(restore_log)
        self.assertEqual(restore_log.changes["is_deleted"]["old"], True)
        self.assertEqual(restore_log.changes["is_deleted"]["new"], False)

    def test_model_hard_delete_signal(self):
        """Verify permanently deleting a model creates a HARD_DELETE audit log."""
        from apps.audit.context import audit_context

        org = Organization.objects.create(
            name="Doomed Org",
            slug="doomed-org",
            created_by=self.user,
        )
        org_id = str(org.id)

        with audit_context(actor=self.user, request_id="req-del-999"):
            org.hard_delete()

        log = ActivityLog.objects.filter(
            object_id=org_id,
            action=ActivityLog.ACTION_HARD_DELETE,
        ).first()

        self.assertIsNotNone(log)
        self.assertEqual(log.actor, self.user)
        self.assertEqual(log.request_id, "req-del-999")

    def test_auth_security_signals(self):
        """Verify Django auth signals trigger ActivityLog entries."""
        from django.contrib.auth import user_logged_in, user_logged_out, user_login_failed
        from apps.audit.context import audit_context

        with audit_context(ip="127.0.0.1", user_agent="AuthTestClient/1.0"):
            # 1. Login signal
            user_logged_in.send(sender=User, request=None, user=self.user)
            login_log = ActivityLog.objects.filter(
                actor=self.user,
                action=ActivityLog.ACTION_LOGIN,
            ).first()
            self.assertIsNotNone(login_log)
            self.assertEqual(login_log.status, ActivityLog.STATUS_SUCCESS)

            # 2. Logout signal
            user_logged_out.send(sender=User, request=None, user=self.user)
            logout_log = ActivityLog.objects.filter(
                actor=self.user,
                action=ActivityLog.ACTION_LOGOUT,
            ).first()
            self.assertIsNotNone(logout_log)

            # 3. Login failed signal
            user_login_failed.send(
                sender=User,
                credentials={"username": "malicious_actor"},
                request=None,
            )
            failed_log = ActivityLog.objects.filter(
                action=ActivityLog.ACTION_LOGIN_FAILED,
            ).first()
            self.assertIsNotNone(failed_log)
            self.assertEqual(failed_log.status, ActivityLog.STATUS_FAILURE)
            self.assertEqual(failed_log.metadata.get("attempted_username"), "malicious_actor")


class DynamicModelAuditIntegrationTests(TestCase):
    """
    Verify declarative dynamic models created via apps.meta_engine
    automatically integrate with the activity audit trail.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from apps.meta_engine.models import MetaModel, MetaField
        from apps.meta_engine.schema_engine import DynamicSchemaEngine
        from apps.meta_engine.model_factory import DynamicModelFactory

        cls.meta_model = MetaModel.objects.create(
            name="audit_deal",
            label="Audit Deal",
            app_label="audit_test",
            table_name="app_test_audit_deal",
            is_tenant_aware=True,
            is_soft_delete=True,
            is_auditable=True,
        )
        MetaField.objects.create(
            model=cls.meta_model,
            name="title",
            field_type="char",
            label="Deal Title",
        )
        MetaField.objects.create(
            model=cls.meta_model,
            name="amount",
            field_type="integer",
            label="Deal Amount",
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
        self.user = User.objects.create_user(username="dynaudituser", email="dynaudit@test.com", password="pw")
        self.org = Organization.objects.create(name="Dynamic Org", slug="dynamic-org")

    def test_dynamic_model_audit_lifecycle(self):
        from apps.audit.context import audit_context
        from apps.tenants.context import tenant_context

        # 1. CREATE dynamic record
        with tenant_context(self.org):
            with audit_context(actor=self.user, request_id="req-dyn-create"):
                deal = self.dynamic_cls.objects.create(title="Series A Investment", amount=1000000)

        create_log = ActivityLog.objects.filter(
            object_id=str(deal.id),
            action=ActivityLog.ACTION_CREATE,
        ).first()

        self.assertIsNotNone(create_log)
        self.assertEqual(create_log.actor, self.user)
        self.assertEqual(create_log.organization, self.org)
        self.assertEqual(create_log.request_id, "req-dyn-create")
        self.assertEqual(create_log.changes["title"]["new"], "Series A Investment")
        self.assertEqual(create_log.changes["amount"]["new"], 1000000)

        # 2. UPDATE dynamic record
        with tenant_context(self.org):
            with audit_context(actor=self.user, request_id="req-dyn-update"):
                deal.amount = 1500000
                deal.save()

        update_log = ActivityLog.objects.filter(
            object_id=str(deal.id),
            action=ActivityLog.ACTION_UPDATE,
        ).first()

        self.assertIsNotNone(update_log)
        self.assertEqual(update_log.changes["amount"]["old"], 1000000)
        self.assertEqual(update_log.changes["amount"]["new"], 1500000)

        # 3. SOFT DELETE dynamic record
        with tenant_context(self.org):
            with audit_context(actor=self.user, request_id="req-dyn-del"):
                deal.delete()

        delete_log = ActivityLog.objects.filter(
            object_id=str(deal.id),
            action=ActivityLog.ACTION_DELETE,
        ).first()

        self.assertIsNotNone(delete_log)
        self.assertEqual(delete_log.changes["is_deleted"]["old"], False)
        self.assertEqual(delete_log.changes["is_deleted"]["new"], True)


from rest_framework.test import APITestCase
from django.contrib.admin.sites import AdminSite


class ActivityLogAdminTests(TestCase):
    """Verify read-only restrictions and formatted displays in Django Admin."""

    def setUp(self):
        from apps.audit.admin import ActivityLogAdmin
        self.site = AdminSite()
        self.admin = ActivityLogAdmin(ActivityLog, self.site)
        self.user = User.objects.create_user(username="adminauditor", password="pw")
        self.log = ActivityLog.objects.create(
            actor=self.user,
            action=ActivityLog.ACTION_UPDATE,
            status=ActivityLog.STATUS_SUCCESS,
            object_repr="Test Target Object",
            changes={"name": {"old": "Alpha", "new": "Beta"}},
            metadata={"source": "admin_test"},
        )

    def test_admin_permissions_are_strictly_read_only(self):
        self.assertFalse(self.admin.has_add_permission(None))
        self.assertFalse(self.admin.has_change_permission(None))
        self.assertFalse(self.admin.has_delete_permission(None))

    def test_admin_custom_displays(self):
        action_html = self.admin.action_badge(self.log)
        self.assertIn("Update", action_html)

        status_html = self.admin.status_badge(self.log)
        self.assertIn("Success", status_html)

        diff_html = self.admin.changes_diff_card(self.log)
        self.assertIn("Alpha", diff_html)
        self.assertIn("Beta", diff_html)

        meta_html = self.admin.metadata_display(self.log)
        self.assertIn("admin_test", meta_html)


class ActivityLogAPITests(APITestCase):
    """Verify ActivityLog REST API endpoints and tenant scoping."""

    def setUp(self):
        self.org1 = Organization.objects.create(name="Org One", slug="org-one")
        self.org2 = Organization.objects.create(name="Org Two", slug="org-two")

        self.user1 = User.objects.create_user(username="user1", password="pw")
        self.superuser = User.objects.create_superuser(username="admin", email="admin@test.com", password="pw")

        self.log1 = ActivityLog.objects.create(
            organization=self.org1,
            actor=self.user1,
            action=ActivityLog.ACTION_CREATE,
            object_repr="Org 1 Doc",
        )
        self.log2 = ActivityLog.objects.create(
            organization=self.org2,
            action=ActivityLog.ACTION_CREATE,
            object_repr="Org 2 Doc",
        )

    def test_unauthenticated_access_blocked(self):
        response = self.client.get("/api/v1/audit/logs/")
        self.assertEqual(response.status_code, 401)

    def test_authenticated_tenant_scoped_access(self):
        self.client.force_authenticate(user=self.user1)
        response = self.client.get("/api/v1/audit/logs/?workspace=org-one")
        self.assertEqual(response.status_code, 200)
        results = response.data if isinstance(response.data, list) else response.data.get("results", [])
        ids = [item["id"] for item in results]
        self.assertIn(str(self.log1.id), ids)
        self.assertNotIn(str(self.log2.id), ids)

    def test_superuser_global_access(self):
        self.client.force_authenticate(user=self.superuser)
        response = self.client.get("/api/v1/audit/logs/")
        self.assertEqual(response.status_code, 200)
        results = response.data if isinstance(response.data, list) else response.data.get("results", [])
        ids = [item["id"] for item in results]
        self.assertIn(str(self.log1.id), ids)
        self.assertIn(str(self.log2.id), ids)

    def test_retrieve_single_log(self):
        self.client.force_authenticate(user=self.superuser)
        response = self.client.get(f"/api/v1/audit/logs/{self.log1.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], str(self.log1.id))
        self.assertEqual(response.data["action"], ActivityLog.ACTION_CREATE)

    def test_read_only_mutations_disallowed(self):
        self.client.force_authenticate(user=self.superuser)
        # POST
        res_post = self.client.post("/api/v1/audit/logs/", {"action": "create"})
        self.assertEqual(res_post.status_code, 405)
        # PUT
        res_put = self.client.put(f"/api/v1/audit/logs/{self.log1.id}/", {"action": "update"})
        self.assertEqual(res_put.status_code, 405)
        # DELETE
        res_del = self.client.delete(f"/api/v1/audit/logs/{self.log1.id}/")
        self.assertEqual(res_del.status_code, 405)




