/**
 * Dynamic Provider & Model Selector for Hermes Agent Profiles in Django Admin.
 * Handles dependent dropdown loading, token pricing display, context window metrics,
 * and supported input/output modality badges.
 * Supports both standalone ProfileAdmin and ProfileInline inside CustomUserAdmin.
 */

document.addEventListener('DOMContentLoaded', function () {
    // Shared cache of fetched models per provider across all form instances
    const modelsCache = {};

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

    function initProviderModelWidget(providerSelect) {
        if (!providerSelect || providerSelect.dataset.modelsWidgetInitialized) return;
        providerSelect.dataset.modelsWidgetInitialized = 'true';

        // Derive name prefix to match companion model_name select (e.g. 'profile-0-' in ProfileInline or '' in standalone)
        const providerName = providerSelect.name || '';
        let prefix = '';
        if (providerName.endsWith('-provider')) {
            prefix = providerName.slice(0, -'provider'.length);
        } else if (providerName.endsWith('provider') && providerName !== 'provider') {
            prefix = providerName.slice(0, -'provider'.length);
        }

        // Scope lookup to parent container (fieldset / inline row / form)
        const formContainer = providerSelect.closest('.inline-related, fieldset, form') || document;
        const modelSelect = (prefix ? formContainer.querySelector(`select[name="${prefix}model_name"]`) : null) ||
                            formContainer.querySelector('select.hermes-model-select') ||
                            document.getElementById(`id_${prefix}model_name`) ||
                            document.getElementById('id_model_name') ||
                            formContainer.querySelector('select[name$="model_name"]');

        if (!modelSelect) {
            return;
        }

        // Create specifications card styled for full-width responsive layout (no horizontal overflow)
        const card = document.createElement('div');
        card.className = 'hermes-model-specs-card';
        card.style.display = 'none';
        card.style.width = '100%';
        card.style.maxWidth = '100%';
        card.style.minWidth = '0';
        card.style.boxSizing = 'border-box';
        card.style.clear = 'both';
        card.style.marginTop = '12px';
        card.style.marginBottom = '6px';
        card.style.padding = '14px 18px';
        card.style.borderRadius = '8px';
        card.style.background = '#1e293b';
        card.style.color = '#f8fafc';
        card.style.border = '1px solid #334155';
        card.style.fontSize = '13px';
        card.style.lineHeight = '1.5';
        card.style.boxShadow = '0 3px 10px rgba(0,0,0,0.2)';

        // Locate form row container and ensure it supports block flow beneath the select
        const formRow = modelSelect.closest('.form-row') || modelSelect.closest('.fieldBox') || modelSelect.closest('p') || modelSelect.parentNode;
        if (formRow) {
            formRow.style.display = 'block';
            formRow.style.width = '100%';
            formRow.style.boxSizing = 'border-box';
            // Clean up any stale card instance
            const oldCard = formRow.querySelector('.hermes-model-specs-card');
            if (oldCard) oldCard.remove();
            formRow.appendChild(card);
        } else {
            modelSelect.parentNode.appendChild(card);
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
                ? `<span style="background: #065f46; color: #6ee7b7; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600;">🧠 Reasoning Supported</span>`
                : `<span style="background: #334155; color: #94a3b8; padding: 2px 8px; border-radius: 4px; font-size: 11px;">Standard Inference</span>`;

            const inMods = modelData.input_modalities && modelData.input_modalities.length > 0 ? modelData.input_modalities : ['text'];
            const outMods = modelData.output_modalities && modelData.output_modalities.length > 0 ? modelData.output_modalities : ['text'];

            const inBadgesHtml = inMods.map(m => renderModalityBadge(m)).join('');
            const outBadgesHtml = outMods.map(m => renderModalityBadge(m)).join('');
            const hasSpecialOutput = outMods.some(m => m.toLowerCase() !== 'text');

            card.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; border-bottom: 1px solid #334155; padding-bottom: 8px;">
                    <div style="display: flex; align-items: center; flex-wrap: wrap; gap: 8px;">
                        <span style="font-weight: 700; color: #38bdf8; font-size: 14px; letter-spacing: 0.2px;">⚡ Model Specifications & Pricing</span>
                        ${reasoningBadge}
                    </div>
                    <span style="background: #0f172a; border: 1px solid #334155; padding: 2px 10px; border-radius: 4px; font-size: 11px; font-weight: 600; color: #94a3b8; text-transform: uppercase;">${providerSelect.value}</span>
                </div>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin-bottom: 12px;">
                    <div style="background: rgba(15, 23, 42, 0.4); padding: 8px 12px; border-radius: 6px; border: 1px solid #334155;">
                        <span style="color: #94a3b8; display: block; font-size: 11px; font-weight: 600; text-transform: uppercase; margin-bottom: 2px;">Context Window</span>
                        <strong style="color: #f1f5f9; font-size: 14px;">${ctx}</strong>
                    </div>
                    <div style="background: rgba(15, 23, 42, 0.4); padding: 8px 12px; border-radius: 6px; border: 1px solid #334155;">
                        <span style="color: #94a3b8; display: block; font-size: 11px; font-weight: 600; text-transform: uppercase; margin-bottom: 2px;">Input Cost (/1M tokens)</span>
                        <strong style="color: #4ade80; font-size: 14px;">${inCost}</strong>
                    </div>
                    <div style="background: rgba(15, 23, 42, 0.4); padding: 8px 12px; border-radius: 6px; border: 1px solid #334155;">
                        <span style="color: #94a3b8; display: block; font-size: 11px; font-weight: 600; text-transform: uppercase; margin-bottom: 2px;">Output Cost (/1M tokens)</span>
                        <strong style="color: #fb923c; font-size: 14px;">${outCost}</strong>
                    </div>
                </div>
                <div style="margin-bottom: 12px; padding: 10px 12px; background: rgba(15, 23, 42, 0.6); border-radius: 6px; border: 1px solid #334155;">
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
                <div style="color: #cbd5e1; font-size: 12px; font-style: italic; line-height: 1.4;">${desc}</div>
            `;
            card.style.display = 'block';
        }

        async function loadModelsForProvider(provider, selectedModelId = null) {
            if (!provider) return;

            let models = modelsCache[provider];
            if (!models) {
                modelSelect.disabled = true;
                // Show subtle loading indication inside specs card
                card.style.display = 'block';
                card.innerHTML = `
                    <div style="display: flex; align-items: center; gap: 8px; color: #94a3b8; font-size: 12px; padding: 4px 0;">
                        <span>⏳</span>
                        <span>Loading specifications for <strong>${provider.toUpperCase()}</strong> models...</span>
                    </div>
                `;

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

            // Preserve currentVal if it was custom/unlisted
            if (currentVal && !activeModelData) {
                const customOpt = document.createElement('option');
                customOpt.value = currentVal;
                customOpt.textContent = `${currentVal} (Current / Custom)`;
                customOpt.selected = true;
                modelSelect.insertBefore(customOpt, modelSelect.firstChild);
                activeModelData = {
                    id: currentVal,
                    name: currentVal,
                    provider: provider,
                    description: 'Custom or uncataloged model ID.',
                    context_length: 128000,
                    cost_input_per_1m: 0,
                    cost_output_per_1m: 0,
                    supports_reasoning: false,
                    input_modalities: ['text'],
                    output_modalities: ['text']
                };
            }

            // If no active model matched and no custom option, default to first option
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
    }

    // Initialize all matching provider select elements (standalone Profile form and User ProfileInline)
    function initAll() {
        document.querySelectorAll('select.hermes-provider-select, select[name="provider"], select[name$="-provider"], select#id_provider').forEach(initProviderModelWidget);
    }

    initAll();

    // Support dynamically added inlines (e.g. via Django Admin inline formset events)
    if (window.django && window.django.jQuery) {
        window.django.jQuery(document).on('formset:added', function (event, $row) {
            if ($row && $row.length) {
                $row[0].querySelectorAll('select.hermes-provider-select, select[name$="provider"]').forEach(initProviderModelWidget);
            }
        });
    }
});
