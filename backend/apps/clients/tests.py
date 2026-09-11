"""
Unit tests for Client Management (apps.clients).
"""

from decimal import Decimal
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework.authtoken.models import Token

from apps.tenants.models import Organization
from apps.clients.models import Client
from apps.clients.admin import ClientAdmin
from apps.integration.models import Profile


class ClientModelTestCase(TestCase):
    """
    Unit tests validating Client data model, multi-tenancy, and AI budget logic.
    """

    def setUp(self):
        self.org1 = Organization.objects.create(name="Tenant One", slug="tenant-1")
        self.org2 = Organization.objects.create(name="Tenant Two", slug="tenant-2")

    def test_client_creation_and_defaults(self):
        client = Client.objects.create(
            organization=self.org1,
            name="Acme Corporation",
            slug="acme-corp",
            primary_contact_name="Alice Smith",
            primary_contact_email="alice@acme.com"
        )
        self.assertEqual(str(client), "Acme Corporation (Tenant One)")
        self.assertTrue(client.is_ai_enabled)
        self.assertEqual(client.ai_budget_usd, Decimal("15.00"))
        self.assertEqual(client.ai_spend_usd, Decimal("0.0000"))
        self.assertEqual(client.ai_budget_percentage, 0.0)
        self.assertEqual(client.ai_budget_status, "healthy")
        self.assertTrue(client.can_use_ai())

    def test_unique_slug_per_organization(self):
        Client.objects.create(
            organization=self.org1,
            name="Acme One",
            slug="acme"
        )
        # Same slug under different org is allowed
        client2 = Client.objects.create(
            organization=self.org2,
            name="Acme Two",
            slug="acme"
        )
        self.assertIsNotNone(client2.id)

        # Same slug under same org must raise IntegrityError
        with self.assertRaises(IntegrityError):
            Client.objects.create(
                organization=self.org1,
                name="Acme Duplicate",
                slug="acme"
            )

    def test_ai_budget_status_milestones(self):
        client = Client.objects.create(
            organization=self.org1,
            name="Budget Corp",
            slug="budget-corp",
            ai_budget_usd=Decimal("100.00"),
            ai_spend_usd=Decimal("20.00")
        )
        # 20% -> healthy
        self.assertEqual(client.ai_budget_status, "healthy")
        self.assertTrue(client.can_use_ai())

        # 55% -> velocity_check
        client.ai_spend_usd = Decimal("55.00")
        self.assertEqual(client.ai_budget_percentage, 55.0)
        self.assertEqual(client.ai_budget_status, "velocity_check")
        self.assertTrue(client.can_use_ai())

        # 80% -> warning
        client.ai_spend_usd = Decimal("80.00")
        self.assertEqual(client.ai_budget_percentage, 80.0)
        self.assertEqual(client.ai_budget_status, "warning")
        self.assertTrue(client.can_use_ai())

        # 105% -> exceeded
        client.ai_spend_usd = Decimal("105.00")
        self.assertEqual(client.ai_budget_percentage, 105.0)
        self.assertEqual(client.ai_budget_status, "exceeded")
        self.assertFalse(client.can_use_ai())

    def test_can_use_ai_gatekeeper_disabled(self):
        client = Client.objects.create(
            organization=self.org1,
            name="Disabled AI Corp",
            slug="disabled-ai",
            is_ai_enabled=False,
            ai_budget_usd=Decimal("100.00"),
            ai_spend_usd=Decimal("0.00")
        )
        self.assertEqual(client.ai_budget_status, "disabled")
        self.assertFalse(client.can_use_ai())

    def test_can_use_ai_gatekeeper_suspended(self):
        client = Client.objects.create(
            organization=self.org1,
            name="Suspended Corp",
            slug="suspended-corp",
            status=Client.STATUS_SUSPENDED,
            ai_budget_usd=Decimal("100.00"),
            ai_spend_usd=Decimal("0.00")
        )
        self.assertFalse(client.can_use_ai())

    def test_one_to_many_users_association(self):
        client = Client.objects.create(
            organization=self.org1,
            name="Multi User Corp",
            slug="multi-user"
        )
        user1 = User.objects.create_user(username="client_rep1", email="rep1@corp.com")
        user2 = User.objects.create_user(username="client_rep2", email="rep2@corp.com")

        # Assign both user profiles to this client
        user1.profile.client = client
        user1.profile.user_type = "client"
        user1.profile.save()

        user2.profile.client = client
        user2.profile.user_type = "client"
        user2.profile.save()

        self.assertEqual(client.linked_users_count, 2)
        linked_usernames = list(client.users.values_list('user__username', flat=True))
        self.assertIn("client_rep1", linked_usernames)
        self.assertIn("client_rep2", linked_usernames)

        # Profile budget delegation
        self.assertEqual(user1.profile.effective_ai_budget_usd, client.ai_budget_usd)
        self.assertEqual(user1.profile.effective_ai_spend_usd, client.ai_spend_usd)


class ClientAPITestCase(APITestCase):
    """
    Tests REST API endpoints for Client management and budget actions.
    """

    def setUp(self):
        self.org = Organization.objects.create(name="Enterprise Firm", slug="enterprise-firm")
        self.staff_user = User.objects.create_superuser(username="admin_staff", email="admin@firm.com", password="password123")
        self.staff_token, _ = Token.objects.get_or_create(user=self.staff_user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.staff_token.key}")

        self.client_entity = Client.objects.create(
            organization=self.org,
            name="Zenith Labs",
            slug="zenith-labs",
            primary_contact_name="Bob Jones",
            primary_contact_email="bob@zenith.com",
            ai_budget_usd=Decimal("50.00"),
            ai_spend_usd=Decimal("10.00")
        )

    def test_list_clients(self):
        res = self.client.get('/api/v1/clients/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        # res.data is a list of clients
        items = res.data if isinstance(res.data, list) else res.data.get('results', [])
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['name'], "Zenith Labs")
        self.assertEqual(items[0]['organization_name'], "Enterprise Firm")

    def test_client_budget_status_action(self):
        url = f"/api/v1/clients/{self.client_entity.id}/budget-status/"
        # GET status
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['percentage_used'], 20.0)
        self.assertEqual(res.data['budget_status'], "healthy")
        self.assertTrue(res.data['can_use_ai'])

        # POST spend delta ($30.00 -> total $40.00 / 80%)
        res_post = self.client.post(url, {"spend_delta_usd": "30.00"}, format='json')
        self.assertEqual(res_post.status_code, status.HTTP_200_OK)
        self.assertEqual(res_post.data['percentage_used'], 80.0)
        self.assertEqual(res_post.data['budget_status'], "warning")
        self.assertTrue(res_post.data['milestones']['advisory_75_reached'])

    def test_hermes_budget_status_endpoint_resolves_client_model(self):
        # Query /api/hermes/client-budget-status/ with client_id="zenith-labs"
        url = f"/api/hermes/client-budget-status/?client_id=zenith-labs"
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['name'], "Zenith Labs")
        self.assertEqual(res.data['slug'], "zenith-labs")
        self.assertEqual(res.data['ai_budget_usd'], "50.00")
        self.assertTrue(res.data['can_use_ai'])
