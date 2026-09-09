"""
Admin Forms for Automation Engine.
"""

from django import forms
from .models import AutomationRule
from .registry import ServiceRegistry


class AutomationRuleAdminForm(forms.ModelForm):
    """
    Custom ModelForm dynamically populating grouped dropdowns for:
    1. target_model: Dynamically grouped by installed Django App
    2. action_type: Dynamically grouped by Service Category (Hermes, Django, Script, Webhook)
    """
    target_model = forms.ChoiceField(
        required=False,
        help_text="Select a Django model to watch for CRUD lifecycle triggers."
    )
    action_type = forms.ChoiceField(
        required=True,
        help_text="Select the service or action handler to execute."
    )

    class Meta:
        model = AutomationRule
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # 1. Populate dynamic model choices
        model_choices = [('', '-- None (Not Model Event) --')]
        model_choices.extend(ServiceRegistry.get_registered_model_choices())
        self.fields['target_model'].choices = model_choices

        # 2. Populate dynamic action choices
        action_choices = [('', '-- Select Action / Service --')]
        action_choices.extend(ServiceRegistry.get_action_choices())
        self.fields['action_type'].choices = action_choices

    def clean(self):
        cleaned_data = super().clean()
        action_type = cleaned_data.get('action_type')

        # Automatically resolve and synchronize action_category
        if action_type:
            action_def = ServiceRegistry.get_action(action_type)
            if action_def:
                cleaned_data['action_category'] = action_def.category

        return cleaned_data
