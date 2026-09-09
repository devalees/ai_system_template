from django import forms
from .models import Profile
from .services import CANONICAL_PROVIDERS, get_models_for_provider
from .services.hermes_discovery import HermesDiscoveryService


class ProfileAdminForm(forms.ModelForm):
    """
    Enhanced Admin Form for Profile model.
    Provides live Hermes profile selector, dynamic provider/model dropdowns,
    and user categorization.
    """
    hermes_profile_name = forms.CharField(
        required=False,
        widget=forms.Select(attrs={'class': 'hermes-profile-select'}),
        help_text="Hermes engine profile folder/slug. Use 🔄 Reload button to refresh live."
    )
    provider = forms.ChoiceField(
        choices=[(p["slug"], p["name"]) for p in CANONICAL_PROVIDERS],
        widget=forms.Select(attrs={'class': 'hermes-provider-select'}),
        help_text="Inference provider used by this profile."
    )
    model_name = forms.CharField(
        widget=forms.Select(attrs={'class': 'hermes-model-select'}),
        help_text="Model selected for this profile. Dynamically loaded based on provider."
    )

    class Meta:
        model = Profile
        fields = [
            'user',
            'is_agent',
            'user_type',
            'hermes_profile_name',
            'display_name',
            'role',
            'provider',
            'model_name',
            'reasoning_effort',
            'is_active',
            'description',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # 1. Populate Hermes Profile Choices
        profiles = HermesDiscoveryService.list_available_profiles()
        profile_choices = [("", "-- Select Hermes Profile --")]
        matched_profile = False
        current_profile = (
            self.instance.hermes_profile_name or self.instance.name
            if (self.instance and self.instance.pk) else ""
        )

        for p in profiles:
            p_name = p["name"]
            if p_name == current_profile:
                matched_profile = True
            profile_choices.append((p_name, f"{p['display_name']} ({p_name})"))

        if current_profile and not matched_profile:
            profile_choices.append((current_profile, f"{current_profile} (Custom / Offline)"))

        self.fields['hermes_profile_name'].widget.choices = profile_choices

        # 2. Populate Model Choices for Active Provider
        active_provider = "openrouter"
        if self.instance and self.instance.pk and self.instance.provider:
            active_provider = self.instance.provider
        elif self.data and "provider" in self.data:
            active_provider = self.data["provider"]

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

        if current_val and not model_found:
            choices.insert(0, (current_val, f"{current_val} (Current Selection)"))

        self.fields['model_name'].widget.choices = choices


# Backward compatibility alias
AgentProfileAdminForm = ProfileAdminForm
