from django import forms
from .models import Profile
from .services import CANONICAL_PROVIDERS, get_models_for_provider, format_modality_indicator
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
            'provider_credential',
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
        grouped_choices = {}
        model_found = False
        current_val = self.instance.model_name if (self.instance and self.instance.pk) else ""

        for m in models:
            m_id = m["id"]
            if m_id == current_val:
                model_found = True
            ctx_k = f"{m.get('context_length', 128000) // 1000}k" if m.get('context_length') else "128k"
            in_c = f"${m.get('cost_input_per_1m', 0):.3f}"
            out_c = f"${m.get('cost_output_per_1m', 0):.3f}"
            mod_badge = format_modality_indicator(m.get("input_modalities"))
            label = f"{m.get('name', m_id)}  [{mod_badge}] ({ctx_k} ctx | in: {in_c} | out: {out_c})"


            group_name = m.get("provider_group") or "Other"
            if group_name not in grouped_choices:
                grouped_choices[group_name] = []
            grouped_choices[group_name].append((m_id, label))

        choices = []
        if current_val and not model_found:
            choices.append(("", [(current_val, f"{current_val} (Current Selection)")]))

        for group_name in sorted(grouped_choices.keys()):
            choices.append((group_name, grouped_choices[group_name]))

        self.fields['model_name'].widget.choices = choices


# Backward compatibility alias
AgentProfileAdminForm = ProfileAdminForm


from .models import ProviderCredential

class ProviderCredentialAdminForm(forms.ModelForm):
    """
    Admin form for ProviderCredential with masked password widget for API keys.
    """
    api_key = forms.CharField(
        widget=forms.PasswordInput(render_value=False, attrs={
            'placeholder': 'Enter new or updated API Key...',
            'autocomplete': 'new-password',
            'style': 'width: 380px;'
        }),
        required=False,
        help_text="Enter the secret API key. Leave blank to retain existing key."
    )

    class Meta:
        model = ProviderCredential
        fields = [
            'name',
            'provider_type',
            'api_key',
            'base_url',
            'is_default',
            'is_active',
            'organization',
            'metadata',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.encrypted_api_key:
            self.fields['api_key'].help_text = (
                f"Current key: <code>{self.instance.masked_key}</code>. "
                "Enter a new key here only if you want to rotate/change it."
            )

    def save(self, commit=True):
        instance = super().save(commit=False)
        raw_key = self.cleaned_data.get('api_key')
        if raw_key:
            instance.api_key = raw_key
        if commit:
            instance.save()
            self.save_m2m()
        return instance

