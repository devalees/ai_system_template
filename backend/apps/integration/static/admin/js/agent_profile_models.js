/**
 * Dynamic Provider & Model Selector for Hermes Agent Profiles in Django Admin.
 * Handles dependent dropdown loading, token pricing display, and context window metrics.
 */

document.addEventListener('DOMContentLoaded', function () {
    const providerSelect = document.getElementById('id_provider');
    const modelSelect = document.getElementById('id_model_name');

    if (!providerSelect || !modelSelect) {
        return;
    }

    // Cache of fetched models per provider
    const modelsCache = {};

    // Create and inject the live metrics card container below modelSelect
    const card = document.createElement('div');
    card.id = 'hermes-model-specs-card';
    card.style.marginTop = '10px';
    card.style.padding = '12px 16px';
    card.style.borderRadius = '8px';
    card.style.background = '#1e293b';
    card.style.color = '#f8fafc';
    card.style.border = '1px solid #334155';
    card.style.fontSize = '13px';
    card.style.lineHeight = '1.5';
    card.style.maxWidth = '750px';
    card.style.boxShadow = '0 2px 6px rgba(0,0,0,0.15)';
    card.style.display = 'none';

    modelSelect.parentNode.appendChild(card);

    function formatNumber(num) {
        return num ? Number(num).toLocaleString() : 'N/A';
    }

    function updateCard(modelData) {
        if (!modelData) {
            card.style.display = 'none';
            return;
        }

        const ctx = modelData.context_length ? `${formatNumber(modelData.context_length)} tokens` : '128,000 tokens';
        const inCost = modelData.cost_input_per_1m !== undefined ? `$${Number(modelData.cost_input_per_1m).toFixed(3)}` : 'N/A';
        const outCost = modelData.cost_output_per_1m !== undefined ? `$${Number(modelData.cost_output_per_1m).toFixed(3)}` : 'N/A';
        const desc = modelData.description || 'Standard inference model.';

        card.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; border-bottom: 1px solid #475569; padding-bottom: 6px;">
                <span style="font-weight: 600; color: #38bdf8; font-size: 14px;">⚡ Model Specifications & Pricing</span>
                <span style="background: #0f172a; padding: 2px 8px; border-radius: 4px; font-size: 11px; color: #94a3b8;">${providerSelect.value.toUpperCase()}</span>
            </div>
            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 8px;">
                <div>
                    <span style="color: #94a3b8; display: block; font-size: 11px;">CONTEXT WINDOW</span>
                    <strong style="color: #f1f5f9; font-size: 13px;">${ctx}</strong>
                </div>
                <div>
                    <span style="color: #94a3b8; display: block; font-size: 11px;">INPUT COST (/1M)</span>
                    <strong style="color: #4ade80; font-size: 13px;">${inCost}</strong>
                </div>
                <div>
                    <span style="color: #94a3b8; display: block; font-size: 11px;">OUTPUT COST (/1M)</span>
                    <strong style="color: #fb923c; font-size: 13px;">${outCost}</strong>
                </div>
            </div>
            <div style="color: #cbd5e1; font-size: 12px; font-style: italic;">${desc}</div>
        `;
        card.style.display = 'block';
    }

    async function loadModelsForProvider(provider, selectedModelId = null) {
        if (!provider) return;

        let models = modelsCache[provider];
        if (!models) {
            modelSelect.disabled = true;
            try {
                const res = await fetch(`/api/hermes/models/?provider=${encodeURIComponent(provider)}`);
                if (res.ok) {
                    const data = await res.json();
                    models = data.models || [];
                    modelsCache[provider] = models;
                }
            } catch (err) {
                console.error('Failed to load models for provider:', err);
            } finally {
                modelSelect.disabled = false;
            }
        }

        if (!models || models.length === 0) {
            card.style.display = 'none';
            return;
        }

        const currentVal = selectedModelId || modelSelect.value;
        modelSelect.innerHTML = '';

        let activeModelData = null;

        models.forEach(m => {
            const opt = document.createElement('option');
            opt.value = m.id;
            const ctxK = m.context_length ? `${Math.round(m.context_length / 1000)}k` : '128k';
            const inC = `$${(m.cost_input_per_1m || 0).toFixed(3)}`;
            const outC = `$${(m.cost_output_per_1m || 0).toFixed(3)}`;
            opt.textContent = `${m.name || m.id} (${ctxK} ctx | in: ${inC} | out: ${outC})`;

            if (m.id === currentVal) {
                opt.selected = true;
                activeModelData = m;
            }
            modelSelect.appendChild(opt);
        });

        // If current value wasn't found in list, default to first option
        if (!activeModelData && models.length > 0) {
            modelSelect.selectedIndex = 0;
            activeModelData = models[0];
        }

        updateCard(activeModelData);
    }

    // Provider change event
    providerSelect.addEventListener('change', function () {
        loadModelsForProvider(this.value);
    });

    // Model selection change event
    modelSelect.addEventListener('change', function () {
        const provider = providerSelect.value;
        const models = modelsCache[provider] || [];
        const selected = models.find(m => m.id === this.value);
        if (selected) {
            updateCard(selected);
        }
    });

    // Initial trigger on page load
    if (providerSelect.value) {
        loadModelsForProvider(providerSelect.value, modelSelect.value);
    }
});
