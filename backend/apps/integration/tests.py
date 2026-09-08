from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from .models import HandshakeLog, AgentTask

class IntegrationAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_health_check_endpoint(self):
        """Verify that GET /api/health/ returns HTTP 200 and expected schema."""
        url = reverse('api-health')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('status', response.data)
        self.assertIn('database', response.data)
        self.assertIn('server_time', response.data)

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

    def test_agent_task_crud(self):
        """Verify AgentTask creation and query."""
        task = AgentTask.objects.create(
            task_name="test_macro_collection",
            agent_name="hermes-agent",
            input_payload={"country": "US"},
            status="pending"
        )
        url = reverse('agent-task-detail', kwargs={'pk': task.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['task_name'], 'test_macro_collection')
