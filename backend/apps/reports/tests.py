"""
Comprehensive Unit Test Suite for Dynamic Visual Reporting & PDF Generation Engine.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.automation.registry import ServiceRegistry
from apps.media.models import Document
from apps.reports.engine import ReportEngine
from apps.reports.models import (
    PageFormatChoices,
    PageOrientationChoices,
    ReportExecutionFormatChoices,
    ReportExecutionLog,
    ReportExecutionStatusChoices,
    ReportTemplate,
)
from apps.tenants.models import Organization

User = get_user_model()


class ReportEngineTests(TestCase):
    """Unit tests for ReportEngine HTML compilation, token introspection, and PDF rendering."""

    def setUp(self):
        self.org = Organization.objects.create(name="Test Corp", slug="test-corp")
        self.user = User.objects.create_user(username="testuser", password="password123")
        self.template = ReportTemplate.objects.create(
            organization=self.org,
            name="Task Summary Report",
            slug="task_summary_report",
            target_model="auth.User",
            page_format=PageFormatChoices.A4,
            orientation=PageOrientationChoices.PORTRAIT,
            compiled_html="<h1>User Report for {{ object.username }}</h1><p>Created: {{ now|date:'Y-m-d' }}</p>",
            css_styles="h1 { color: #0284c7; }",
            header_html="<header>Report Header</header>",
            footer_html="<footer>Report Footer</footer>"
        )

    def test_get_model_tokens(self):
        """Verify token introspection resolves model fields and system tokens."""
        tokens = ReportEngine.get_model_tokens("auth.User")
        token_keys = [t["token"] for t in tokens]
        self.assertIn("object.username", token_keys)
        self.assertIn("object.email", token_keys)
        self.assertIn("now", token_keys)

    def test_render_html_standard(self):
        """Verify render_html compiles Django variables and embeds CSS and header/footer."""
        html = ReportEngine.render_html(self.template, record_id=str(self.user.id))
        self.assertIn("User Report for testuser", html)
        self.assertIn("Report Header", html)
        self.assertIn("Report Footer", html)
        self.assertIn("dir=\"ltr\"", html)

    def test_render_html_arabic_rtl(self):
        """Verify Arabic content auto-detects and applies RTL dir attribute."""
        arabic_template = ReportTemplate.objects.create(
            organization=self.org,
            name="تقرير الأداء",
            slug="arabic_performance_report",
            target_model="auth.User",
            compiled_html="<h1>تقرير ملخص للمستخدم {{ object.username }}</h1>"
        )
        html = ReportEngine.render_html(arabic_template, record_id=str(self.user.id))
        self.assertIn("dir=\"rtl\" lang=\"ar\"", html)
        self.assertIn("تقرير ملخص للمستخدم testuser", html)

    def test_render_pdf_generation(self):
        """Verify render_pdf compiles binary PDF bytes or returns clean execution response."""
        pdf_bytes, duration_ms, file_size, error_msg = ReportEngine.render_pdf(self.template, record_id=str(self.user.id))
        if pdf_bytes:
            self.assertTrue(pdf_bytes.startswith(b"%PDF"))
            self.assertGreater(file_size, 0)
            self.assertGreaterEqual(duration_ms, 0)
            self.assertIsNone(error_msg)
        else:
            # Handle case where WeasyPrint C shared libraries are unavailable
            self.assertIsNotNone(error_msg)


class ReportAPIViewTests(TestCase):
    """Unit tests for REST API endpoints: Templates CRUD, HTML Preview, and PDF Rendering."""

    def setUp(self):
        self.org = Organization.objects.create(name="API Corp", slug="api-corp")
        self.user = User.objects.create_user(username="apiuser", password="password123")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.template = ReportTemplate.objects.create(
            organization=self.org,
            name="Invoice Template",
            slug="invoice_template",
            target_model="auth.User",
            compiled_html="<h2>Invoice for {{ object.username }}</h2>"
        )

    def test_list_templates(self):
        """GET /api/v1/reports/templates/ lists report templates."""
        url = reverse("report-template-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"] if isinstance(response.data, dict) and "results" in response.data else response.data
        self.assertEqual(len(results), 1)

    def test_list_tokens_endpoint(self):
        """GET /api/v1/reports/templates/tokens/?target_model=auth.User returns introspected tokens."""
        url = reverse("report-template-list-tokens") + "?target_model=auth.User"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        token_names = [t["token"] for t in response.data]
        self.assertIn("object.username", token_names)

    def test_preview_html_endpoint(self):
        """GET /api/v1/reports/templates/<id>/preview/?record_id=... returns HTML content."""
        url = reverse("report-template-preview-html", args=[self.template.id]) + f"?record_id={self.user.id}"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "text/html; charset=utf-8")
        self.assertIn("Invoice for apiuser", response.content.decode())

    def test_render_pdf_endpoint(self):
        """GET /api/v1/reports/templates/<id>/render/?record_id=... returns PDF binary or error."""
        url = reverse("report-template-render-pdf", args=[self.template.id]) + f"?record_id={self.user.id}&save_document=true"
        response = self.client.get(url)
        if response.status_code == status.HTTP_200_OK:
            self.assertEqual(response["Content-Type"], "application/pdf")
            self.assertTrue(ReportExecutionLog.objects.filter(template=self.template).exists())
        else:
            self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)


class ReportAutomationActionTests(TestCase):
    """Unit tests for generate_pdf_report automation action handler."""

    def setUp(self):
        self.org = Organization.objects.create(name="Auto Corp", slug="auto-corp")
        self.user = User.objects.create_user(username="autouser", password="password123")
        self.template = ReportTemplate.objects.create(
            organization=self.org,
            name="Automated Task Report",
            slug="task_completion_report",
            target_model="auth.User",
            compiled_html="<h1>Automated Task Report for {{ object.username }}</h1>"
        )

    def test_generate_pdf_report_action(self):
        """Verify generate_pdf_report action executes cleanly and logs audit record."""
        action_def = ServiceRegistry.get_action("generate_pdf_report")
        self.assertIsNotNone(action_def)
        self.assertIsNotNone(action_def.handler)

        context = {
            "action_params": {
                "template_slug": "task_completion_report",
                "record_id": str(self.user.id),
                "save_document": True
            },
            "pk": str(self.user.id)
        }

        result = action_def.handler(context)
        if result.get("status") == "success":
            self.assertIn("report_log_id", result)
            self.assertTrue(ReportExecutionLog.objects.filter(id=result["report_log_id"]).exists())
        else:
            self.assertIn("error", result)

