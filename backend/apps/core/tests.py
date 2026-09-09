"""
Unit Tests for apps.core foundations, abstract models, and middleware.
"""

import time
import uuid
from django.contrib.auth import get_user_model
from django.db import connection, models
from django.test import RequestFactory, TestCase
from django.test.utils import isolate_apps

from apps.core.middleware import (
    CurrentUserMiddleware,
    _current_user_ctx,
    get_current_authenticated_user,
    get_current_user,
)
from apps.core.models import (
    AuditableModel,
    SoftDeleteModel,
    TimeStampedModel,
    UUIDModel,
)

User = get_user_model()


class ConcreteSampleModel(UUIDModel, TimeStampedModel, SoftDeleteModel, AuditableModel):
    """Concrete model created specifically to verify abstract base models."""
    name = models.CharField(max_length=100)

    class Meta:
        app_label = "core"


class CoreAbstractBaseModelTests(TestCase):
    """Test suite verifying abstract base model functionality."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Dynamically build the table for ConcreteSampleModel during test run
        with connection.schema_editor() as editor:
            editor.create_model(ConcreteSampleModel)

    @classmethod
    def tearDownClass(cls):
        # Drop the table cleanly after test run
        with connection.schema_editor() as editor:
            editor.delete_model(ConcreteSampleModel)
        super().tearDownClass()

    def setUp(self):
        self.user = User.objects.create_user(username="test_auditor", password="password123")
        self.factory = RequestFactory()

    def test_uuid_and_timestamp_generation(self):
        """Verify UUIDv4 primary key and auto timestamping."""
        item = ConcreteSampleModel.objects.create(name="Alpha")
        self.assertIsInstance(item.id, uuid.UUID)
        self.assertIsNotNone(item.created_at)
        self.assertIsNotNone(item.updated_at)

        old_updated = item.updated_at
        time.sleep(0.01)
        item.name = "Alpha Updated"
        item.save()
        self.assertGreater(item.updated_at, old_updated)

    def test_soft_delete_and_restore(self):
        """Verify that soft delete excludes records from standard QuerySet and can be restored."""
        item = ConcreteSampleModel.objects.create(name="Beta")
        self.assertFalse(item.is_deleted)
        self.assertIsNone(item.deleted_at)

        # Soft delete
        item.delete()
        self.assertTrue(item.is_deleted)
        self.assertIsNotNone(item.deleted_at)

        # Standard objects manager excludes it
        self.assertEqual(ConcreteSampleModel.objects.filter(name="Beta").count(), 0)
        # all_objects manager finds it
        self.assertEqual(ConcreteSampleAll := ConcreteSampleModel.all_objects.filter(name="Beta").count(), 1)
        # dead manager finds it
        self.assertEqual(ConcreteSampleModel.objects.dead().filter(name="Beta").count(), 1)

        # Restore
        item.restore()
        self.assertFalse(item.is_deleted)
        self.assertIsNone(item.deleted_at)
        self.assertEqual(ConcreteSampleModel.objects.filter(name="Beta").count(), 1)

    def test_hard_delete(self):
        """Verify hard delete permanently purges record."""
        item = ConcreteSampleModel.objects.create(name="Gamma")
        item.hard_delete()
        self.assertEqual(ConcreteSampleModel.all_objects.filter(name="Gamma").count(), 0)

    def test_auditable_model_with_current_user_middleware(self):
        """Verify created_by and updated_by auto-population via CurrentUserMiddleware."""
        request = self.factory.get("/")
        request.user = self.user

        middleware = CurrentUserMiddleware(lambda req: ConcreteSampleModel.objects.create(name="Audited Record"))
        item = middleware(request)

        self.assertEqual(item.created_by, self.user)
        self.assertEqual(item.updated_by, self.user)

    def test_middleware_cleanup(self):
        """Verify context variable is reset after request finishes to prevent leaks."""
        request = self.factory.get("/")
        request.user = self.user

        def sample_view(req):
            self.assertEqual(get_current_authenticated_user(), self.user)
            return "OK"

        middleware = CurrentUserMiddleware(sample_view)
        middleware(request)

        # Outside middleware invocation, context variable must be None
        self.assertIsNone(get_current_authenticated_user())


class CryptoSecretTests(TestCase):
    """Test suite for secret encryption, decryption, and masking."""

    def test_encryption_and_decryption(self):
        from apps.core.crypto import encrypt_secret, decrypt_secret, mask_secret

        secret = "sk-live-antigravity-998877665544"
        encrypted = encrypt_secret(secret)
        self.assertNotEqual(secret, encrypted)

        decrypted = decrypt_secret(encrypted)
        self.assertEqual(decrypted, secret)

    def test_secret_masking(self):
        from apps.core.crypto import mask_secret

        secret = "sk-live-antigravity-secret"
        masked = mask_secret(secret, visible_chars=4)
        self.assertTrue(masked.startswith("sk-l"))
        self.assertTrue(masked.endswith("cret"))
        self.assertIn("•", masked)


class SettingsRegistryTests(TestCase):
    """Test suite verifying setting definitions, type validation, and registry."""

    def test_setting_type_validations(self):
        from apps.core.settings_registry import Setting
        from django.core.exceptions import ValidationError

        # int
        s_int = Setting(data_type="int", default=10)
        self.assertEqual(s_int.validate("42"), 42)
        with self.assertRaises(ValidationError):
            s_int.validate("not_a_number")

        # bool
        s_bool = Setting(data_type="bool", default=False)
        self.assertTrue(s_bool.validate("true"))
        self.assertTrue(s_bool.validate("yes"))
        self.assertTrue(s_bool.validate("1"))
        self.assertFalse(s_bool.validate("false"))

        # float
        s_float = Setting(data_type="float", default=1.5)
        self.assertEqual(s_float.validate("3.14"), 3.14)

        # choice
        s_choice = Setting(data_type="choice", default="light", choices=[("light", "Light"), ("dark", "Dark")])
        self.assertEqual(s_choice.validate("dark"), "dark")
        with self.assertRaises(ValidationError):
            s_choice.validate("neon")

        # json
        s_json = Setting(data_type="json", default={})
        self.assertEqual(s_json.validate('{"key": "val"}'), {"key": "val"})

    def test_decorator_registration(self):
        from apps.core.settings_registry import Setting, register_settings_group, settings_registry

        @register_settings_group("test_app", verbose_name="Test Application", icon="🧪", order=15)
        class TestAppSettings:
            SAMPLE_KEY = Setting(data_type="str", default="hello_world")
            NUM_WORKERS = Setting(data_type="int", default=4)

        group = settings_registry.get_group("test_app")
        self.assertIsNotNone(group)
        self.assertEqual(group.verbose_name, "Test Application")
        self.assertEqual(group.icon, "🧪")

        sample_setting = settings_registry.get_setting_definition("test_app", "SAMPLE_KEY")
        self.assertIsNotNone(sample_setting)
        self.assertEqual(sample_setting.default, "hello_world")

