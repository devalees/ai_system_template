from django import forms
from .models import AutomationRule
from .registry import ServiceRegistry


class AutomationRuleAdminForm(forms.ModelForm):
    """
    Custom ModelForm dynamically populating grouped dropdowns for:
    1. trigger_model: Source Django model to watch for lifecycle triggers
    2. target_model: Destination Django model for automated CRUD record operations
    3. action_type: Registered service or action handler
    """
    trigger_model = forms.ChoiceField(
        required=False,
        help_text="Select a source Django model to watch for CRUD lifecycle triggers."
    )
    target_model = forms.ChoiceField(
        required=False,
        help_text="Select a destination Django model for automated CRUD operations."
    )
    action_type = forms.ChoiceField(
        required=False,
        help_text="Select the service or action handler to execute (optional if Target CRUD is specified)."
    )

    class Meta:
        model = AutomationRule
        fields = '__all__'
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2}),
            'filter_conditions': forms.Textarea(attrs={'rows': 3, 'style': 'font-family: monospace; font-size: 12px;'}),
            'condition_rules': forms.Textarea(attrs={'rows': 4, 'style': 'font-family: monospace; font-size: 12px;'}),
            'field_mappings': forms.Textarea(attrs={'rows': 4, 'style': 'font-family: monospace; font-size: 12px;'}),
            'action_params': forms.Textarea(attrs={'rows': 3, 'style': 'font-family: monospace; font-size: 12px;'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # 1. Populate dynamic model choices for trigger and target models
        model_choices = [('', '-- None / No Model --')]
        model_choices.extend(ServiceRegistry.get_registered_model_choices())
        self.fields['trigger_model'].choices = model_choices
        self.fields['target_model'].choices = model_choices

        # 2. Populate dynamic action choices
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

        # Automatically resolve and synchronize action_category
        if action_type:
            action_def = ServiceRegistry.get_action(action_type)
            if action_def:
                cleaned_data['action_category'] = action_def.category

        return cleaned_data
