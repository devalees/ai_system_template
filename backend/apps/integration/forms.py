from django import forms
from .models import AgentProfile
from .services import CANONICAL_PROVIDERS, get_models_for_provider

class AgentProfileAdminForm(forms.ModelForm):
    provider = forms.ChoiceField(
        choices=[(p["slug"], p["name"]) for p in CANONICAL_PROVIDERS],
        widget=forms.Select(attrs={'class': 'hermes-provider-select'}),
        help_text="Inference provider used by this agent profile."
    )
    model_name = forms.CharField(
        widget=forms.Select(attrs={'class': 'hermes-model-select'}),
        help_text="Model selected for this profile. Dynamically loaded based on provider."
    )

    class Meta:
        model = AgentProfile
        fields = [
            'name',
            'display_name',
            'role',
            'provider',
            'model_name',
            'is_active',
            'description',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Determine active provider to pre-populate model choices on initial server render
        active_provider = "openrouter"
        if self.instance and self.instance.pk and self.instance.provider:
            active_provider = self.instance.provider
        elif self.data and "provider" in self.data:
            active_provider = self.data["provider"]

        # Pre-seed model choices for server validation and initial dropdown render
        models = get_models_for_provider(active_provider)
        choices = []
        model_found = False
        current_val = self.instance.model_name if (self.instance and self.instance.pk) else ""

        for m in models:
            m_id = m["id"]
            if m_id == current_val:
                model_found = True
            ctx_k = f"{m.get('context_length', 128000) // 1000}k" if m.get('context_length') else "128k"
            in_c = f"${m.get('cost_input_per_1m', 0):.3f}"
            out_c = f"${m.get('cost_output_per_1m', 0):.3f}"
            label = f"{m.get('name', m_id)}  ({ctx_k} ctx | in: {in_c} | out: {out_c})"
            choices.append((m_id, label))

        # If current value is not in fetched top models, keep it as valid choice
        if current_val and not model_found:
            choices.insert(0, (current_val, f"{current_val} (Current Selection)"))

        self.fields['model_name'].widget.choices = choices
