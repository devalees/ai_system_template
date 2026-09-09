"""
AI Agents & Hermes Integration Settings Registration.
"""

from django.utils.translation import gettext_lazy as _
from apps.core.settings_registry import Setting, register_settings_group


@register_settings_group(
    app_label="integration",
    verbose_name=_("AI Agents & Hermes"),
    icon="🤖",
    order=30
)
class IntegrationSettings:
    DEFAULT_PROVIDER = Setting(
        data_type="choice",
        default="openrouter",
        choices=[
            ("openrouter", "OpenRouter"),
            ("anthropic", "Anthropic"),
            ("openai-api", "OpenAI"),
            ("gemini", "Google Gemini"),
            ("deepseek", "DeepSeek"),
        ],
        verbose_name=_("Default Inference Provider"),
        help_text=_("Default LLM provider when provisioning or selecting new agent profiles.")
    )
    DEFAULT_MODEL = Setting(
        data_type="str",
        default="google/gemini-2.5-flash",
        verbose_name=_("Default Agent Model"),
        help_text=_("Foundation model assigned to new agent profiles by default.")
    )
    DEFAULT_REASONING_EFFORT = Setting(
        data_type="choice",
        default="medium",
        choices=[
            ("none", _("None")),
            ("low", _("Low")),
            ("medium", _("Medium")),
            ("high", _("High")),
            ("max", _("Max")),
        ],
        verbose_name=_("Default Reasoning Effort"),
        help_text=_("Default thinking budget allocated to new agent profiles.")
    )
    DAILY_BUDGET_CAP_USD = Setting(
        data_type="float",
        default=50.0,
        verbose_name=_("Daily Token Budget Cap ($)"),
        help_text=_("Global daily token expenditure ceiling across all agent executions.")
    )
