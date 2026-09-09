from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient
from .models import HandshakeLog, AgentProfile, SpendReport, AgentTask

class IntegrationAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        # Seed all profiles, RBAC groups, bot users, and tokens
        call_command('seed_profiles')

        self.orchestrator_token = Token.objects.get(user__username='bot_orchestrator').key
        self.cost_token = Token.objects.get(user__username='bot_cost_controller').key
        self.qa_token = Token.objects.get(user__username='bot_qa_auditor').key
        self.comms_token = Token.objects.get(user__username='bot_comms_agent').key
        self.archivist_token = Token.objects.get(user__username='bot_archivist').key

        self.orchestrator_profile = AgentProfile.objects.get(name='orchestrator')
        self.qa_profile = AgentProfile.objects.get(name='qa_auditor')

    def test_health_check_endpoint_is_public(self):
        """Verify that GET /api/health/ is publicly accessible."""
        url = reverse('api-health')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('status', response.data)
        self.assertIn('database', response.data)
        self.assertEqual(response.data['active_profiles_count'], 5)

    def test_handshake_endpoint_is_public(self):
        """Verify that POST /api/handshake/ accepts boot handshakes without prior token."""
        url = reverse('api-handshake')
        payload = {
            "agent_id": "test-hermes-agent",
            "version": "1.0.0",
            "message": "Hello from Hermes test runner",
            "metadata": {"test_run": True}
        }
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], 'acknowledged')
        self.assertEqual(HandshakeLog.objects.count(), 1)

    def test_unauthenticated_requests_rejected(self):
        """Verify that protected API endpoints return 401 Unauthorized without Token."""
        urls = [
            reverse('agent-profile-list'),
            reverse('agent-task-list'),
            reverse('spend-report-list'),
        ]
        for url in urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED, f"Expected 401 on {url}")

    def test_authenticated_agent_profiles_list(self):
        """Verify that any authenticated bot with view_agentprofile can list profiles."""
        url = reverse('agent-profile-list')
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.orchestrator_token}')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 5)

    def test_cost_controller_can_post_spend_reports(self):
        """Verify that bot_cost_controller can successfully ingest spend reports."""
        url = reverse('spend-report-list')
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.cost_token}')
        payload = {
            "reported_by": "cost_controller",
            "total_api_calls": 15,
            "total_tokens": 82000,
            "total_cost_usd": "0.0125",
            "daily_budget_usd": "10.00",
            "budget_status": "OK",
            "payload": {"details": "daily ledger"}
        }
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        report = SpendReport.objects.first()
        self.assertEqual(report.reported_by, 'cost_controller')
        self.assertEqual(report.created_by.username, 'bot_cost_controller')

    def test_rbac_cost_controller_cannot_create_tasks(self):
        """Verify RBAC defense: bot_cost_controller is blocked from creating tasks (403 Forbidden)."""
        url = reverse('agent-task-list')
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.cost_token}')
        payload = {
            "task_name": "Unauthorized task from cost controller",
            "assigned_profile": self.orchestrator_profile.id,
        }
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_rbac_orchestrator_can_create_tasks_but_not_spend_reports(self):
        """Verify RBAC defense: orchestrator can create tasks but cannot forge spend reports."""
        # Orchestrator creates task -> 201 Created
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.orchestrator_token}')
        task_url = reverse('agent-task-list')
        response = self.client.post(task_url, {
            "task_name": "Decompose user architecture request",
            "assigned_profile": self.orchestrator_profile.id,
            "input_payload": {"spec": "RBAC"},
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(AgentTask.objects.first().created_by.username, 'bot_orchestrator')

        # Orchestrator attempts to create spend report -> 403 Forbidden
        spend_url = reverse('spend-report-list')
        spend_resp = self.client.post(spend_url, {
            "reported_by": "orchestrator",
            "total_api_calls": 5,
            "total_tokens": 1000,
            "total_cost_usd": "0.0010",
        }, format='json')
        self.assertEqual(spend_resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_qa_auditor_verdict_review_gate(self):
        """Verify that ONLY QA Auditor can submit verdicts on tasks under review."""
        task = AgentTask.objects.create(
            task_name="Verify security boundaries",
            assigned_profile=self.orchestrator_profile,
            status="review"
        )
        verdict_url = reverse('agent-task-submit-verdict', kwargs={'pk': task.id})

        # 1. Cost controller attempts verdict -> 403 Forbidden
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.cost_token}')
        resp_blocked = self.client.post(verdict_url, {"verdict": "approved"}, format='json')
        self.assertEqual(resp_blocked.status_code, status.HTTP_403_FORBIDDEN)

        # 2. QA Auditor submits verdict -> 200 OK
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.qa_token}')
        resp_approved = self.client.post(verdict_url, {
            "verdict": "approved",
            "notes": "RBAC boundaries verified empirically."
        }, format='json')
        self.assertEqual(resp_approved.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_approved.data['new_task_status'], 'completed')

        task.refresh_from_db()
        self.assertEqual(task.status, 'completed')
        self.assertEqual(task.review_verdict, 'approved')

    def test_agent_profile_reasoning_effort(self):
        """Verify reasoning_effort configuration on AgentProfile."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.orchestrator_token}')
        url = reverse('agent-profile-detail', kwargs={'name': 'qa_auditor'})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['reasoning_effort'], 'high')

    def test_user_post_save_signal_creates_profile(self):
        """Verify standard Django lifecycle: creating User auto-generates linked Profile."""
        new_user = User.objects.create(username="jane_analyst", email="jane@example.com")
        self.assertTrue(hasattr(new_user, "profile"))
        self.assertIsNotNone(new_user.profile)
        self.assertFalse(new_user.profile.is_agent)
        self.assertEqual(new_user.profile.user_type, "client")

    def test_hermes_profiles_discovery_endpoint(self):
        """Verify GET /api/hermes/profiles/ discovers and returns live Hermes engine profiles."""
        url = reverse('hermes-profiles')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("profiles", resp.data)
        self.assertGreaterEqual(resp.data["count"], 5)
        names = [p["name"] for p in resp.data["profiles"]]
        self.assertIn("orchestrator", names)
        self.assertIn("cost_controller", names)
        self.assertIn("qa_auditor", names)

