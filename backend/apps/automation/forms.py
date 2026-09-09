"""
Admin Forms for Centralized Automation Engine.
"""

from django import forms
from .models import AutomationTrigger, AutomationAction, AutomationRule
from .registry import ServiceRegistry


class AutomationTriggerAdminForm(forms.ModelForm):
    """
    Form for configuring AutomationTrigger (WHEN an event occurs).
    Populates dynamic choices for trigger_model.
    """
    trigger_model = forms.ChoiceField(
        required=False,
        help_text="Select a source Django model to watch for CRUD lifecycle triggers."
    )

    class Meta:
        model = AutomationTrigger
        fields = '__all__'
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2}),
            'filter_conditions': forms.Textarea(attrs={'rows': 3, 'style': 'font-family: monospace; font-size: 12px;'}),
            'condition_rules': forms.Textarea(attrs={'rows': 4, 'style': 'font-family: monospace; font-size: 12px;'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        model_choices = [('', '-- None / No Model --')]
        model_choices.extend(ServiceRegistry.get_registered_model_choices())
        self.fields['trigger_model'].choices = model_choices


class AutomationActionAdminForm(forms.ModelForm):
    """
    Form for configuring AutomationAction (WHAT happens).
    Populates dynamic choices for target_model and action_type.
    """
    target_model = forms.ChoiceField(
        required=False,
        help_text="Select a destination Django model for automated CRUD operations."
    )
    action_type = forms.ChoiceField(
        required=False,
        help_text="Select the service or action handler to execute (optional if Target CRUD is specified)."
    )

    class Meta:
        model = AutomationAction
        fields = '__all__'
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2}),
            'field_mappings': forms.Textarea(attrs={'rows': 3, 'style': 'font-family: monospace; font-size: 12px;'}),
            'action_params': forms.Textarea(attrs={'rows': 3, 'style': 'font-family: monospace; font-size: 12px;'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        model_choices = [('', '-- None / No Model --')]
        model_choices.extend(ServiceRegistry.get_registered_model_choices())
        self.fields['target_model'].choices = model_choices

        action_choices = [('', '-- None (Target CRUD Only) --')]
        action_choices.extend(ServiceRegistry.get_action_choices())
        self.fields['action_type'].choices = action_choices

    def clean(self):
        cleaned_data = super().clean()
        action_type = cleaned_data.get('action_type')
        target_model = cleaned_data.get('target_model')
        target_operation = cleaned_data.get('target_operation')

        if not action_type and not (target_model and target_operation):
            raise forms.ValidationError(
                "You must specify either a Target Model CRUD operation (target_model + target_operation) "
                "or a registered Action Handler."
            )

        if action_type:
            action_def = ServiceRegistry.get_action(action_type)
            if action_def:
                cleaned_data['action_category'] = action_def.category

        return cleaned_data


# Backward-compatibility alias
AutomationRuleAdminForm = AutomationTriggerAdminForm
