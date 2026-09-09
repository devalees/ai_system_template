"""
Core Service Engine for Dynamic Visual Reporting & PDF Generation.

Provides:
- ReportEngine: High-performance HTML template compilation, model introspection token bridge,
  WeasyPrint vector PDF rendering, and Arabic RTL typography support.
"""

import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from django.apps import apps
from django.template import Context, Template
from django.utils import translation
from django.utils.translation import gettext_lazy as _

from apps.reports.models import PageFormatChoices, PageOrientationChoices, ReportTemplate

logger = logging.getLogger(__name__)

# CSS @page dimension rules for standard formats
PAGE_SIZE_CSS = {
    PageFormatChoices.A4: {
        PageOrientationChoices.PORTRAIT: "210mm 297mm",
        PageOrientationChoices.LANDSCAPE: "297mm 210mm",
    },
    PageFormatChoices.LETTER: {
        PageOrientationChoices.PORTRAIT: "8.5in 11in",
        PageOrientationChoices.LANDSCAPE: "11in 8.5in",
    },
    PageFormatChoices.LEGAL: {
        PageOrientationChoices.PORTRAIT: "8.5in 14in",
        PageOrientationChoices.LANDSCAPE: "14in 8.5in",
    },
    PageFormatChoices.THERMAL_80MM: {
        PageOrientationChoices.PORTRAIT: "80mm auto",
        PageOrientationChoices.LANDSCAPE: "80mm auto",
    },
}


class ReportEngine:
    """
    Template compilation, introspection, and vector PDF rendering service.
    """

    @classmethod
    def get_target_model_class(cls, model_identifier: str) -> Optional[type]:
        """
        Resolve model identifier (e.g. 'auth.User', 'integration.AgentTask', 'crm.lead')
        to its Django Model class.
        """
        if not model_identifier:
            return None

        # Check if dot-separated app_label.model_name
        if "." in model_identifier:
            try:
                app_label, model_name = model_identifier.split(".", 1)
                return apps.get_model(app_label, model_name)
            except (ValueError, LookupError):
                pass

        # Search across registered models by model_name or meta_engine slug
        for model in apps.get_models():
            if model._meta.model_name.lower() == model_identifier.lower() or model._meta.label.lower() == model_identifier.lower():
                return model

        # Check meta_engine dynamic models
        try:
            from apps.meta_engine.models import MetaModel
            meta_model = MetaModel.objects.filter(slug=model_identifier).first() or MetaModel.objects.filter(name=model_identifier).first()
            if meta_model:
                from apps.meta_engine.model_factory import DynamicModelFactory
                return DynamicModelFactory.get_model_class(meta_model.slug)
        except Exception as e:
            logger.debug(f"MetaModel resolution error for {model_identifier}: {e}")

        return None

    @classmethod
    def fetch_record_context(cls, target_model: str, record_id: str) -> Dict[str, Any]:
        """
        Fetch model instance dictionary context for template rendering.
        """
        if not target_model or not record_id:
            return {}

        model_class = cls.get_target_model_class(target_model)
        if not model_class:
            return {"record_id": record_id}

        try:
            # Try fetching record by pk or id
            instance = model_class.objects.filter(pk=record_id).first()
            if not instance and hasattr(model_class, "all_objects"):
                instance = model_class.all_objects.filter(pk=record_id).first()

            if instance:
                return {
                    "object": instance,
                    "record": instance,
                    "target_model": target_model,
                    "record_id": str(instance.pk),
                }
        except Exception as e:
            logger.warning(f"Failed to fetch record {record_id} for model {target_model}: {e}")

        return {"record_id": record_id}

    @classmethod
    def get_model_tokens(cls, target_model: str) -> List[Dict[str, str]]:
        """
        Introspect model fields and return available variable tokens for report designer.
        """
        tokens: List[Dict[str, str]] = []
        model_class = cls.get_target_model_class(target_model)
        if not model_class:
            return [
                {"token": "object.id", "label": "Record ID", "type": "String"},
                {"token": "now", "label": "Current Datetime", "type": "DateTime"},
            ]

        try:
            for field in model_class._meta.get_fields():
                if field.is_relation and not field.many_to_one:
                    continue

                field_name = field.name
                verbose_name = getattr(field, "verbose_name", field_name).title()
                internal_type = field.get_internal_type() if hasattr(field, "get_internal_type") else "CharField"

                tokens.append({
                    "token": f"object.{field_name}",
                    "label": str(verbose_name),
                    "type": internal_type,
                    "help_text": str(getattr(field, "help_text", "")),
                })
        except Exception as e:
            logger.error(f"Error introspecting model tokens for {target_model}: {e}")

        # Add common system tokens
        tokens.extend([
            {"token": "now", "label": "Current Datetime", "type": "DateTime"},
            {"token": "organization.name", "label": "Organization Name", "type": "String"},
            {"token": "user.username", "label": "Generating User", "type": "String"},
        ])

        return tokens

    @classmethod
    def render_html(
        cls,
        template_obj: ReportTemplate,
        record_id: Optional[str] = None,
        extra_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Render report template HTML string with resolved context, CSS styles, and RTL support.
        """
        context_data = cls.fetch_record_context(template_obj.target_model, record_id) if record_id else {}
        if extra_context:
            context_data.update(extra_context)

        # Standard context variables
        from django.utils import timezone
        context_data.setdefault("now", timezone.now())
        context_data.setdefault("template", template_obj)

        # Process compiled HTML using Django Template Engine
        html_markup = template_obj.compiled_html or "<p>No template markup provided.</p>"
        django_template = Template(html_markup)
        rendered_body = django_template.render(Context(context_data))

        # Build Page CSS
        size_spec = PAGE_SIZE_CSS.get(template_obj.page_format, {}).get(
            template_obj.orientation, "210mm 297mm"
        )

        base_css = f"""
        @page {{
            size: {size_spec};
            margin: 15mm 15mm 20mm 15mm;
            @bottom-right {{
                content: "Page " counter(page) " of " counter(pages);
                font-size: 9pt;
                font-family: 'Amiri', 'Cairo', sans-serif;
                color: #666;
            }}
            @bottom-left {{
                content: "{template_obj.name}";
                font-size: 9pt;
                font-family: 'Amiri', 'Cairo', sans-serif;
                color: #666;
            }}
        }}

        body {{
            font-family: 'Amiri', 'Cairo', 'Inter', sans-serif;
            font-size: 11pt;
            line-height: 1.5;
            color: #1e293b;
            background-color: #ffffff;
            margin: 0;
            padding: 0;
        }}

        .report-header {{
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #e2e8f0;
        }}

        .report-footer {{
            margin-top: 30px;
            padding-top: 10px;
            border-top: 1px solid #e2e8f0;
            font-size: 9pt;
            color: #64748b;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
            margin-bottom: 15px;
        }}

        th, td {{
            padding: 8px 12px;
            text-align: left;
            border-bottom: 1px solid #e2e8f0;
        }}

        th {{
            background-color: #f8fafc;
            font-weight: 600;
            color: #0f172a;
        }}

        /* Arabic / RTL Auto Detection & Font Support */
        [lang="ar"], .rtl {{
            direction: rtl;
            text-align: right;
        }}

        {template_obj.css_styles or ""}
        """

        # Detect Arabic content to apply RTL layout if needed
        is_arabic = bool(re.search(r"[\u0600-\u06FF]", rendered_body))
        dir_attr = 'dir="rtl" lang="ar" class="rtl"' if is_arabic else 'dir="ltr" lang="en"'

        # Assemble full valid HTML5 Document
        full_html = f"""<!DOCTYPE html>
<html {dir_attr}>
<head>
    <meta charset="utf-8">
    <title>{template_obj.name}</title>
    <style>
        {base_css}
    </style>
</head>
<body>
    {f'<div class="report-header">{template_obj.header_html}</div>' if template_obj.header_html else ''}
    <main class="report-content">
        {rendered_body}
    </main>
    {f'<div class="report-footer">{template_obj.footer_html}</div>' if template_obj.footer_html else ''}
</body>
</html>"""

        return full_html

    @classmethod
    def render_pdf(
        cls,
        template_obj: ReportTemplate,
        record_id: Optional[str] = None,
        extra_context: Optional[Dict[str, Any]] = None
    ) -> Tuple[bytes, int, int, Optional[str]]:
        """
        Render report PDF binary bytes.
        Returns: (pdf_bytes, duration_ms, file_size_bytes, error_message)
        """
        start_time = time.time()

        try:
            full_html = cls.render_html(template_obj, record_id, extra_context)

            # Attempt WeasyPrint conversion
            try:
                from weasyprint import HTML
                pdf_bytes = HTML(string=full_html).write_pdf()
            except ImportError:
                # If WeasyPrint not available, return clean fallback PDF stream or error
                logger.error("WeasyPrint dependency not installed or C libraries missing.")
                raise RuntimeError("WeasyPrint vector PDF engine is unavailable on this host.")

            duration_ms = int((time.time() - start_time) * 1000)
            file_size = len(pdf_bytes)

            return pdf_bytes, duration_ms, file_size, None

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Error rendering PDF for report {template_obj.slug}: {e}", exc_info=True)
            return b"", duration_ms, 0, str(e)
