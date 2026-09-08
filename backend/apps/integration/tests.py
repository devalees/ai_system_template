from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from .models import HandshakeLog, AgentProfile, SpendReport, AgentTask

class IntegrationAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.profile = AgentProfile.objects.create(
            name="orchestrator",
            display_name="Chief of Staff",
            role="orchestrator",
            description="Intake and routing",
            model_name="google/gemini-2.5-flash",
            provider="openrouter",
            is_active=True
        )

    def test_health_check_endpoint(self):
        """Verify that GET /api/health/ returns HTTP 200 and expected schema."""
        url = reverse('api-health')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('status', response.data)
        self.assertIn('database', response.data)
        self.assertIn('server_time', response.data)
        self.assertEqual(response.data['active_profiles_count'], 1)

    def test_handshake_endpoint_success(self):
        """Verify that POST /api/handshake/ accepts agent payload and persists log."""
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
        self.assertEqual(response.data['received_agent_id'], 'test-hermes-agent')
        self.assertIn('log_id', response.data)

        # Check DB persistence
        self.assertEqual(HandshakeLog.objects.count(), 1)
        log = HandshakeLog.objects.first()
        self.assertEqual(log.agent_id, 'test-hermes-agent')
        self.assertEqual(log.status, 'success')

    def test_agent_profiles_list(self):
        """Verify listing registered agent profiles via GET /api/profiles/."""
        url = reverse('agent-profile-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'orchestrator')

    def test_spend_report_ingestion(self):
        """Verify POST /api/spend-reports/ for cost controller."""
        url = reverse('spend-report-list')
        payload = {
            "reported_by": "cost_controller",
            "total_api_calls": 12,
            "total_tokens": 73000,
            "total_cost_usd": "0.0117",
            "daily_budget_usd": "10.00",
            "budget_status": "OK",
            "payload": {"details": "test report"}
        }
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(SpendReport.objects.count(), 1)
        report = SpendReport.objects.first()
        self.assertEqual(report.budget_status, 'OK')

    def test_agent_task_verdict_review_cycle(self):
        """Verify task review gate: submit_verdict changes status to completed."""
        task = AgentTask.objects.create(
            task_name="Write financial summary",
            assigned_profile=self.profile,
            input_payload={"quarter": "Q3"},
            status="review"
        )
        url = reverse('agent-task-submit-verdict', kwargs={'pk': task.id})
        payload = {
            "verdict": "approved",
            "notes": "All figures match the balance sheet."
        }
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['new_task_status'], 'completed')

        task.refresh_from_db()
        self.assertEqual(task.status, 'completed')
        self.assertEqual(task.review_verdict, 'approved')
        self.assertIsNotNone(task.completed_at)

    def test_hermes_providers_endpoint(self):
        """Verify GET /api/hermes/providers/ returns supported providers."""
        url = reverse('hermes-providers')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        slugs = [p['slug'] for p in response.data]
        self.assertIn('openrouter', slugs)
        self.assertIn('anthropic', slugs)
        self.assertIn('openai-api', slugs)

    def test_hermes_models_endpoint(self):
        """Verify GET /api/hermes/models/?provider=anthropic returns models with pricing and context."""
        url = reverse('hermes-models')
        response = self.client.get(url, {'provider': 'anthropic'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['provider'], 'anthropic')
        self.assertTrue(response.data['count'] > 0)
        first_model = response.data['models'][0]
        self.assertIn('id', first_model)
        self.assertIn('context_length', first_model)
        self.assertIn('cost_input_per_1m', first_model)
        self.assertIn('cost_output_per_1m', first_model)
