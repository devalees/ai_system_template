"""
Automated Test Suite for Provider Credentials, Zero-Downtime Sync,
Budget Ceiling Gates, and Multi-Agent Handoff (Phase 22).
"""

from unittest.mock import MagicMock, patch
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.core.config import set_setting
from apps.integration.models import Profile, ProviderCredential, SpendReport, AgentTask
from apps.integration.services.credential_sync import (
    collect_active_provider_keys,
    sync_hermes_runtime_credentials,
    sync_profile_runtime_env,
)
from apps.automation.actions import dispatch_hermes_prompt_action
from apps.automation.engine import AutomationEngine
from apps.automation.models import AutomationTrigger, AutomationAction


class ProviderCredentialModelTests(TestCase):
    """Tests for ProviderCredential model, encryption, masking, and default constraints."""

    def test_credential_encryption_and_masking(self):
        cred = ProviderCredential(name="OpenRouter Test", provider_type="openrouter")
        cred.api_key = "sk-or-v1-secret-token-12345678"
        cred.save()

        # Check raw stored value is encrypted
        self.assertNotEqual(cred.encrypted_api_key, "sk-or-v1-secret-token-12345678")
        self.assertIn(":", cred.encrypted_api_key)

        # Check property decrypts accurately
        self.assertEqual(cred.api_key, "sk-or-v1-secret-token-12345678")

        # Check masked representation
        masked = cred.masked_key
        self.assertTrue(masked.startswith("sk-o"))
        self.assertTrue(masked.endswith("5678"))
        self.assertIn("•", masked)

    def test_single_default_enforcement(self):
        c1 = ProviderCredential.objects.create(name="Key 1", provider_type="openrouter", is_default=True)
        c2 = ProviderCredential.objects.create(name="Key 2", provider_type="openrouter", is_default=True)

        c1.refresh_from_db()
        c2.refresh_from_db()

        self.assertFalse(c1.is_default)
        self.assertTrue(c2.is_default)

    def test_profile_resolve_provider_and_key_hierarchy(self):
        user = User.objects.create_user(username="bot_worker", email="worker@test.com")
        profile = user.profile
        profile.provider = "gemini"
        profile.save()

        # Tier 3: Process environment fallback
        with patch.dict("os.environ", {"GEMINI_API_KEY": "gemini-env-fallback-key"}):
            prov, key, url = profile.resolve_provider_and_key()
            self.assertEqual(prov, "gemini")
            self.assertEqual(key, "gemini-env-fallback-key")

            # Tier 2: Default ProviderCredential overrides environment fallback
            cred_default = ProviderCredential(name="Gemini Default", provider_type="gemini", is_default=True)
            cred_default.api_key = "gemini-default-cred-key"
            cred_default.save()

            prov, key, url = profile.resolve_provider_and_key()
            self.assertEqual(key, "gemini-default-cred-key")

            # Tier 1: Direct assigned ProviderCredential overrides Default
            cred_direct = ProviderCredential(name="Gemini Direct", provider_type="gemini", is_default=False)
            cred_direct.api_key = "gemini-direct-override-key"
            cred_direct.save()

            profile.provider_credential = cred_direct
            profile.save()

            prov, key, url = profile.resolve_provider_and_key()
            self.assertEqual(key, "gemini-direct-override-key")


class CredentialSyncServiceTests(TestCase):
    """Tests for zero-downtime credential collection and runtime sync."""

    def test_collect_active_provider_keys(self):
        cred1 = ProviderCredential(name="OpenRouter Test", provider_type="openrouter", is_default=True)
        cred1.api_key = "sk-or-v1-collected-key"
        cred1.save()

        cred2 = ProviderCredential(name="Groq Test", provider_type="groq", is_default=True)
        cred2.api_key = "gsk_groq_cred_key"
        cred2.save()

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-ant-env-key"}):
            collected = collect_active_provider_keys()
            self.assertEqual(collected.get("OPENROUTER_API_KEY"), "sk-or-v1-collected-key")
            self.assertEqual(collected.get("GROQ_API_KEY"), "gsk_groq_cred_key")
            self.assertEqual(collected.get("ANTHROPIC_API_KEY"), "sk-ant-env-key")

    def test_sync_hermes_runtime_credentials(self):
        cred = ProviderCredential(name="Anthropic Test", provider_type="anthropic", is_default=True)
        cred.api_key = "sk-ant-test-key-999"
        cred.save()

        res = sync_hermes_runtime_credentials()
        self.assertEqual(res["status"], "success")
        self.assertIn("ANTHROPIC_API_KEY", res["keys"])


class BudgetGateAndSpendTrackingTests(TestCase):
    """Tests for pre-execution budget ceiling gate and post-execution token spend tracking."""

    def setUp(self):
        set_setting("integration.DAILY_BUDGET_CAP_USD", 10.0)

    def test_pre_execution_budget_exceeded(self):
        # Create an existing spend report that reaches the cap
        SpendReport.objects.create(
            reported_by="test_budget",
            total_cost_usd=12.0,
            daily_budget_usd=10.0,
        )

        res = dispatch_hermes_prompt_action({"prompt": "Should not run"})
        self.assertEqual(res["status"], "budget_exceeded")
        self.assertIn("Daily token budget cap of $10.00 USD reached", res["error"])

    @patch("requests.post")
    def test_post_execution_spend_and_deliverable_recording(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"content-type": "application/json"}
        mock_resp.json.return_value = {
            "id": "chatcmpl-unit-test",
            "choices": [{"message": {"role": "assistant", "content": "Analysis verdict: Clean."}}],
            "usage": {"prompt_tokens": 1000, "completion_tokens": 200, "total_tokens": 1200}
        }
        mock_post.return_value = mock_resp

        task = AgentTask.objects.create(task_name="Unit Test Verification", agent_name="qa_auditor")

        res = dispatch_hermes_prompt_action({
            "prompt": "Verify deliverables",
            "profile": "qa_auditor",
            "task_id": str(task.id),
        })

        self.assertEqual(res["status"], "dispatched")
        self.assertEqual(res["deliverable"], "Analysis verdict: Clean.")
        self.assertEqual(res["tokens_used"], 1200)
        self.assertGreater(res["cost_usd"], 0)

        # Check AgentTask updated
        task.refresh_from_db()
        self.assertEqual(task.status, "completed")
        self.assertEqual(task.tokens_used, 1200)

        # Check SpendReport generated
        report = SpendReport.objects.filter(reported_by="qa_auditor").first()
        self.assertIsNotNone(report)
        self.assertEqual(report.total_tokens, 1200)


class MultiAgentHandoffPipelineTests(TestCase):
    """Tests for structured deliverable propagation across sequential actions in execute_pipeline."""

    @patch("requests.post")
    def test_pipeline_deliverable_propagation(self, mock_post):
        trigger = AutomationTrigger.objects.create(
            name="Multi-Agent Chained Pipeline",
            trigger_type="manual",
            is_active=True,
        )

        # Action 1: Orchestrator triage
        a1 = AutomationAction.objects.create(
            trigger=trigger,
            name="Orchestrator Step",
            sequence=10,
            action_type="dispatch_hermes_prompt",
            action_params={"profile": "orchestrator", "prompt": "Synthesize plan."},
        )

        # Action 2: QA Auditor review consuming {{deliverable}}
        a2 = AutomationAction.objects.create(
            trigger=trigger,
            name="QA Auditor Step",
            sequence=20,
            action_type="dispatch_hermes_prompt",
            action_params={"profile": "qa_auditor", "prompt": "Audit: {{deliverable}}"},
        )

        def mock_dispatch(*args, **kwargs):
            payload = kwargs.get("json", {})
            prompt_content = payload["messages"][0]["content"]
            resp = MagicMock()
            resp.status_code = 200
            resp.headers = {"content-type": "application/json"}

            if "Synthesize" in prompt_content:
                resp.json.return_value = {
                    "choices": [{"message": {"role": "assistant", "content": "STEP_1_DELIVERABLE_PAYLOAD"}}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
                }
            else:
                # Step 2: verify prompt received Step 1's deliverable
                self.assertIn("STEP_1_DELIVERABLE_PAYLOAD", prompt_content)
                resp.json.return_value = {
                    "choices": [{"message": {"role": "assistant", "content": "QA_APPROVAL_VERDICT"}}],
                    "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
                }
            return resp

        mock_post.side_effect = mock_dispatch

        res = AutomationEngine.execute_pipeline(trigger_id=trigger.id, trigger_context={"force_execution": True})
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["executed_steps"], 2)
        self.assertEqual(res["final_context"]["deliverable"], "QA_APPROVAL_VERDICT")
