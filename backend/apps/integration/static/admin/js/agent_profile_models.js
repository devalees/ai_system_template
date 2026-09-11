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

    function formatModalityIndicator(inputModalities) {
        if (!inputModalities || inputModalities.length === 0) {
            return '💬 Text';
        }
        const inMods = new Set(inputModalities.map(m => String(m).toLowerCase()));
        const icons = [];
        const labels = [];
        if (inMods.has('image')) {
            icons.push('🖼️');
            labels.push('Vision');
        }
        if (inMods.has('file') || inMods.has('pdf')) {
            icons.push('📁');
            labels.push('File');
        }
        if (inMods.has('audio')) {
            icons.push('🎙️');
            labels.push('Audio');
        }
        if (inMods.has('video')) {
            icons.push('🎥');
            labels.push('Video');
        }
        if (icons.length === 0) {
            return '💬 Text';
        }
        if (icons.length === 1) {
            return `${icons[0]} ${labels[0]}`;
        }
        return `${icons.join('')} Multi`;
    }

    const modalityConfig = {
        'text': { label: 'Text', icon: '💬', bg: '#1e293b', border: '#475569', color: '#cbd5e1' },
        'image': { label: 'Vision / Image', icon: '🖼️', bg: '#082f49', border: '#0284c7', color: '#38bdf8' },
        'file': { label: 'Document / File', icon: '📁', bg: '#451a03', border: '#d97706', color: '#fbbf24' },
        'pdf': { label: 'PDF Document', icon: '📁', bg: '#451a03', border: '#d97706', color: '#fbbf24' },
        'audio': { label: 'Audio / Voice', icon: '🎙️', bg: '#3b0764', border: '#9333ea', color: '#c084fc' },
        'video': { label: 'Video', icon: '🎥', bg: '#450a0a', border: '#dc2626', color: '#f87171' }
    };

    function renderModalityBadge(modKey) {
        const key = String(modKey).toLowerCase();
        const conf = modalityConfig[key] || { label: key.toUpperCase(), icon: '🔹', bg: '#1e293b', border: '#475569', color: '#cbd5e1' };
        return `<span style="display: inline-flex; align-items: center; gap: 4px; background: ${conf.bg}; border: 1px solid ${conf.border}; color: ${conf.color}; padding: 2px 8px; border-radius: 9999px; font-size: 11px; font-weight: 500; margin-right: 6px; margin-bottom: 4px;">
            <span>${conf.icon}</span>
            <span>${conf.label}</span>
        </span>`;
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
        const reasoningBadge = modelData.supports_reasoning 
            ? `<span style="background: #065f46; color: #6ee7b7; padding: 2px 6px; border-radius: 4px; font-size: 11px; margin-left: 8px; font-weight: 600;">🧠 Reasoning Supported</span>`
            : `<span style="background: #334155; color: #94a3b8; padding: 2px 6px; border-radius: 4px; font-size: 11px; margin-left: 8px;">Standard Inference</span>`;

        const inMods = modelData.input_modalities && modelData.input_modalities.length > 0 ? modelData.input_modalities : ['text'];
        const outMods = modelData.output_modalities && modelData.output_modalities.length > 0 ? modelData.output_modalities : ['text'];

        const inBadgesHtml = inMods.map(m => renderModalityBadge(m)).join('');
        const outBadgesHtml = outMods.map(m => renderModalityBadge(m)).join('');
        const hasSpecialOutput = outMods.some(m => m.toLowerCase() !== 'text');

        card.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; border-bottom: 1px solid #475569; padding-bottom: 6px;">
                <div style="display: flex; align-items: center; flex-wrap: wrap; gap: 4px;">
                    <span style="font-weight: 600; color: #38bdf8; font-size: 14px;">⚡ Model Specifications & Pricing</span>
                    ${reasoningBadge}
                </div>
                <span style="background: #0f172a; padding: 2px 8px; border-radius: 4px; font-size: 11px; color: #94a3b8;">${providerSelect.value.toUpperCase()}</span>
            </div>
            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 10px;">
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
            <div style="margin-bottom: 10px; padding: 8px 10px; background: rgba(15, 23, 42, 0.6); border-radius: 6px; border: 1px solid #334155;">
                <div style="display: flex; align-items: flex-start; margin-bottom: ${hasSpecialOutput ? '6px' : '0'};">
                    <span style="color: #94a3b8; font-size: 11px; font-weight: 600; min-width: 95px; text-transform: uppercase; padding-top: 3px;">📥 Accepted:</span>
                    <div style="display: flex; flex-wrap: wrap; align-items: center;">${inBadgesHtml}</div>
                </div>
                ${hasSpecialOutput ? `
                <div style="display: flex; align-items: flex-start;">
                    <span style="color: #94a3b8; font-size: 11px; font-weight: 600; min-width: 95px; text-transform: uppercase; padding-top: 3px;">📤 Generated:</span>
                    <div style="display: flex; flex-wrap: wrap; align-items: center;">${outBadgesHtml}</div>
                </div>` : ''}
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

        // Group models by provider_group
        const groups = {};
        models.forEach(m => {
            const groupName = m.provider_group || 'Other';
            if (!groups[groupName]) {
                groups[groupName] = [];
            }
            groups[groupName].push(m);
        });

        const sortedGroupNames = Object.keys(groups).sort((a, b) => a.localeCompare(b));

        sortedGroupNames.forEach(groupName => {
            const optgroup = document.createElement('optgroup');
            optgroup.label = groupName;

            groups[groupName].forEach(m => {
                const opt = document.createElement('option');
                opt.value = m.id;
                const ctxK = m.context_length ? `${Math.round(m.context_length / 1000)}k` : '128k';
                const inC = `$${(m.cost_input_per_1m || 0).toFixed(3)}`;
                const outC = `$${(m.cost_output_per_1m || 0).toFixed(3)}`;
                const modBadge = formatModalityIndicator(m.input_modalities);
                opt.textContent = `${m.name || m.id}  [${modBadge}] (${ctxK} ctx | in: ${inC} | out: ${outC})`;

                if (m.id === currentVal) {
                    opt.selected = true;
                    activeModelData = m;
                }
                optgroup.appendChild(opt);
            });

            modelSelect.appendChild(optgroup);
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
