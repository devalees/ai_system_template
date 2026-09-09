"""
Comprehensive test suite for Developer API Gateway app (APIKey, Authentication, InboundWebhooks, HMAC).
"""

import hmac
import hashlib
import json
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.tenants.models import Organization, OrganizationMembership
from apps.api_gateway.models import APIKey, InboundWebhook, WebhookEvent
from apps.api_gateway.signature import verify_hmac_signature

User = get_user_model()


class APIKeyModelAndAuthTests(APITestCase):
    """Tests for APIKey generation, verification, and APIKeyAuthentication middleware/class."""

    def setUp(self):
        self.organization = Organization.objects.create(
            name="Gateway Test Org",
            slug="gateway-org",
        )
        self.user = User.objects.create_user(
            username="gatewayuser",
            email="gateway@example.com",
            password="Password123!",
        )
        OrganizationMembership.objects.create(
            user=self.user,
            organization=self.organization,
            role="admin",
        )

    def test_api_key_generation_and_verification(self):
        key_obj, raw_key = APIKey.generate_key(
            name="Production Key",
            user=self.user,
            organization=self.organization,
            scopes=["read", "write"],
        )
        self.assertTrue(raw_key.startswith("agy_live_"))
        self.assertEqual(key_obj.prefix, raw_key[:12])
        self.assertTrue(key_obj.verify_key(raw_key))
        self.assertFalse(key_obj.verify_key("agy_live_invalid_key_hash"))

    def test_api_key_expiration(self):
        past_time = timezone.now() - timedelta(hours=1)
        expired_key_obj, raw_key = APIKey.generate_key(
            name="Expired Key",
            user=self.user,
            organization=self.organization,
            expires_at=past_time,
        )
        self.assertTrue(expired_key_obj.is_expired)

    def test_api_key_authentication_header(self):
        key_obj, raw_key = APIKey.generate_key(
            name="Header Auth Key",
            user=self.user,
            organization=self.organization,
        )
        
        # Test request using X-API-Key header
        self.client.credentials(HTTP_X_API_KEY=raw_key)
        response = self.client.get("/api/v1/gateway/keys/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Test request using Authorization: Api-Key header
        self.client.credentials(HTTP_AUTHORIZATION=f"Api-Key {raw_key}")
        response = self.client.get("/api/v1/gateway/keys/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_api_key_ip_allowlist_restriction(self):
        key_obj, raw_key = APIKey.generate_key(
            name="IP Restricted Key",
            user=self.user,
            organization=self.organization,
            allowed_ips=["192.168.1.100"],
        )

        # Access from disallowed IP -> 401 Unauthorized
        self.client.credentials(HTTP_X_API_KEY=raw_key, REMOTE_ADDR="10.0.0.1")
        response = self.client.get("/api/v1/gateway/keys/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        # Access from allowed IP -> 200 OK
        self.client.credentials(HTTP_X_API_KEY=raw_key, REMOTE_ADDR="192.168.1.100")
        response = self.client.get("/api/v1/gateway/keys/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class APIKeyViewSetTests(APITestCase):
    """Tests for APIKey CRUD REST ViewSet."""

    def setUp(self):
        self.organization = Organization.objects.create(name="Key Org", slug="key-org")
        self.user = User.objects.create_user(username="keyuser", email="key@example.com", password="Password123!")
        OrganizationMembership.objects.create(user=self.user, organization=self.organization, role="admin")
        self.client.force_authenticate(user=self.user)
        self.client.credentials(HTTP_X_WORKSPACE_SLUG=self.organization.slug)

    def test_create_api_key_returns_raw_secret_once(self):
        payload = {
            "name": "Integration Key",
            "scopes": ["read", "tasks:create"],
            "allowed_ips": ["127.0.0.1"],
        }
        response = self.client.post("/api/v1/gateway/keys/", data=payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("raw_key", response.data)
        self.assertTrue(response.data["raw_key"].startswith("agy_live_"))

    def test_soft_delete_api_key(self):
        key_obj, _ = APIKey.generate_key(name="To Delete", user=self.user, organization=self.organization)
        response = self.client.delete(f"/api/v1/gateway/keys/{key_obj.id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        key_obj.refresh_from_db()
        self.assertTrue(key_obj.is_deleted)


class InboundWebhookHMACAndIngestTests(APITestCase):
    """Tests for Inbound Webhook ingestion and HMAC verification (GitHub, Stripe, Slack, Custom)."""

    def setUp(self):
        self.organization = Organization.objects.create(name="Webhook Org", slug="webhook-org")
        self.secret = "whsec_test_secret_key_12345"
        self.webhook = InboundWebhook.objects.create(
            name="GitHub Push Webhook",
            endpoint_slug="github-push-events",
            secret_token=self.secret,
            provider=InboundWebhook.PROVIDER_GITHUB,
            organization=self.organization,
        )

    def test_github_webhook_ingest_valid_hmac(self):
        payload = json.dumps({"ref": "refs/heads/main", "repository": {"name": "repo"}}).encode("utf-8")
        computed_sig = hmac.new(self.secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()

        url = f"/api/v1/gateway/webhooks/{self.webhook.endpoint_slug}/ingest/"
        response = self.client.post(
            url,
            data=payload,
            content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256=f"sha256={computed_sig}",
            HTTP_X_GITHUB_EVENT="push",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "received")

        # Verify WebhookEvent stored in database
        event = WebhookEvent.objects.get(id=response.data["event_id"])
        self.assertEqual(event.event_type, "push")
        self.assertEqual(event.status, WebhookEvent.STATUS_PROCESSED)

    def test_github_webhook_ingest_invalid_hmac(self):
        payload = json.dumps({"ref": "refs/heads/main"}).encode("utf-8")
        url = f"/api/v1/gateway/webhooks/{self.webhook.endpoint_slug}/ingest/"
        response = self.client.post(
            url,
            data=payload,
            content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256="sha256=invalid_signature_hash",
            HTTP_X_GITHUB_EVENT="push",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        event = WebhookEvent.objects.get(id=response.data["event_id"])
        self.assertEqual(event.status, WebhookEvent.STATUS_FAILED)
        self.assertIn("signature mismatch", event.error_message.lower())

    def test_custom_provider_hmac_verification(self):
        custom_secret = "custom_secret_key"
        payload_bytes = b'{"action": "ping"}'
        sig = hmac.new(custom_secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()

        is_valid, err = verify_hmac_signature(
            provider="custom",
            secret_token=custom_secret,
            payload_bytes=payload_bytes,
            headers={"X-Signature": sig},
        )
        self.assertTrue(is_valid)
