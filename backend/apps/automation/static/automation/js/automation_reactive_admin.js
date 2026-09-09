/**
 * Reactive Dynamic Admin UI for Centralized Automation Engine.
 *
 * Implements:
 * 1. Dynamic Section Toggling based on trigger_type, event_type, and target_operation
 * 2. AJAX Dynamic Field Introspection for trigger_model (populating trigger_field choices)
 * 3. Interactive Schema Mapping Assistant for target_model (required fields, type badges, quick JSON insertion)
 * 4. Visual Condition Rule builder helpers
 */

document.addEventListener('DOMContentLoaded', function () {
    // Inject Custom Styles for Reactive Panels
    const style = document.createElement('style');
    style.textContent = `
        .auto-schema-panel {
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 14px 18px;
            margin: 12px 0;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
            font-size: 13px;
        }
        .auto-panel-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 10px;
            font-weight: 700;
            color: #1e293b;
        }
        .auto-pill-list {
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            margin: 8px 0;
        }
        .auto-field-pill {
            display: inline-flex;
            align-items: center;
            gap: 5px;
            background: #ffffff;
            border: 1px solid #cbd5e1;
            border-radius: 6px;
            padding: 4px 9px;
            font-family: monospace;
            font-size: 11px;
            cursor: pointer;
            transition: all 0.15s ease;
            color: #334155;
            user-select: none;
        }
        .auto-field-pill:hover {
            border-color: #0284c7;
            background: #f0f9ff;
            color: #0284c7;
            transform: translateY(-1px);
        }
        .auto-field-pill.is-required {
            border-color: #fca5a5;
            background: #fef2f2;
            color: #991b1b;
            font-weight: bold;
        }
        .auto-field-pill.is-required:hover {
            border-color: #ef4444;
            background: #fee2e2;
        }
        .auto-tag-context {
            background: #ecfdf5;
            border: 1px solid #a7f3d0;
            color: #065f46;
            border-radius: 6px;
            padding: 3px 8px;
            font-family: monospace;
            font-size: 11px;
            cursor: pointer;
            transition: all 0.15s ease;
        }
        .auto-tag-context:hover {
            background: #d1fae5;
            border-color: #34d399;
        }
        .auto-badge-info {
            display: inline-block;
            padding: 2px 7px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
            background: #e0f2fe;
            color: #0369a1;
            margin-left: 6px;
        }
        .auto-quick-btn {
            background: #f1f5f9;
            border: 1px solid #cbd5e1;
            color: #475569;
            font-size: 11px;
            font-weight: 600;
            padding: 3px 8px;
            border-radius: 4px;
            cursor: pointer;
            transition: all 0.15s ease;
        }
        .auto-quick-btn:hover {
            background: #e2e8f0;
            color: #0f172a;
        }
    `;
    document.head.appendChild(style);

    // Form inputs
    const triggerTypeSelect = document.querySelector('select[name="trigger_type"]');
    const triggerModelSelect = document.querySelector('select[name="trigger_model"]');
    const triggerFieldInput = document.querySelector('input[name="trigger_field"]');
    const targetModelSelect = document.querySelector('select[name="target_model"]');
    const targetOperationSelect = document.querySelector('select[name="target_operation"]');
    const fieldMappingsArea = document.querySelector('textarea[name="field_mappings"]');
    const conditionRulesArea = document.querySelector('textarea[name="condition_rules"]');

    if (!triggerTypeSelect) {
        return; // Not on AutomationRule change form
    }

    // Identify Fieldsets by headers or contained elements
    function getParentFieldset(element) {
        if (!element) return null;
        return element.closest('fieldset') || element.closest('.module');
    }

    const stateTransitionFieldset = getParentFieldset(triggerFieldInput);
    const targetCrudFieldset = getParentFieldset(targetModelSelect);
    const celeryBeatFieldset = getParentFieldset(document.querySelector('select[name="schedule_unit"]'));

    // 1. CONDITIONAL SECTION TOGGLING
    function updateSectionVisibility() {
        const triggerType = triggerTypeSelect.value;
        const targetOp = targetOperationSelect ? targetOperationSelect.value : '';

        // Model Event vs Time-Based
        if (triggerType === 'model_event') {
            if (celeryBeatFieldset) celeryBeatFieldset.style.display = 'none';
            if (stateTransitionFieldset) stateTransitionFieldset.style.display = '';
        } else if (triggerType === 'time_based') {
            if (celeryBeatFieldset) celeryBeatFieldset.style.display = '';
            if (stateTransitionFieldset) stateTransitionFieldset.style.display = 'none';
        } else {
            // Webhook or Manual
            if (celeryBeatFieldset) celeryBeatFieldset.style.display = 'none';
            if (stateTransitionFieldset) stateTransitionFieldset.style.display = 'none';
        }

        // Target CRUD section
        if (targetCrudFieldset) {
            if (targetOp || (targetModelSelect && targetModelSelect.value)) {
                targetCrudFieldset.classList.remove('collapsed');
            }
        }
    }

    triggerTypeSelect.addEventListener('change', updateSectionVisibility);
    if (targetOperationSelect) {
        targetOperationSelect.addEventListener('change', updateSectionVisibility);
    }
    updateSectionVisibility();

    // 2. TRIGGER MODEL INTROSPECTION (POPULATE FIELD SUGGESTIONS)
    let triggerFieldsCache = [];

    async function introspectTriggerModel() {
        const model = triggerModelSelect.value;
        if (!model) return;

        try {
            const resp = await fetch(`/api/automation/introspection/?model=${encodeURIComponent(model)}`, {
                headers: { 'Accept': 'application/json' }
            });
            if (!resp.ok) return;
            const data = await resp.json();
            triggerFieldsCache = data.fields || [];

            // Add datalist to trigger_field input if present
            if (triggerFieldInput) {
                let datalist = document.getElementById('trigger_fields_datalist');
                if (!datalist) {
                    datalist = document.createElement('datalist');
                    datalist.id = 'trigger_fields_datalist';
                    document.body.appendChild(datalist);
                    triggerFieldInput.setAttribute('list', 'trigger_fields_datalist');
                }
                datalist.innerHTML = '';
                triggerFieldsCache.forEach(f => {
                    const opt = document.createElement('option');
                    opt.value = f.name;
                    opt.label = `${f.name} (${f.type})`;
                    datalist.appendChild(opt);
                });
            }

            // Update badge next to trigger_model
            let badge = document.getElementById('trigger_model_badge');
            if (!badge) {
                badge = document.createElement('span');
                badge.id = 'trigger_model_badge';
                badge.className = 'auto-badge-info';
                triggerModelSelect.parentNode.appendChild(badge);
            }
            badge.textContent = `✓ ${data.verbose_name} (${data.fields.length} fields)`;
        } catch (e) {
            console.warn('Failed to introspect trigger model:', e);
        }
    }

    triggerModelSelect.addEventListener('change', introspectTriggerModel);
    if (triggerModelSelect.value) {
        introspectTriggerModel();
    }

    // 3. TARGET MODEL INTROSPECTION & FIELD MAPPING ASSISTANT
    let targetAssistantPanel = null;

    async function introspectTargetModel() {
        const model = targetModelSelect.value;
        if (!targetAssistantPanel && fieldMappingsArea) {
            targetAssistantPanel = document.createElement('div');
            targetAssistantPanel.className = 'auto-schema-panel';
            fieldMappingsArea.parentNode.insertBefore(targetAssistantPanel, fieldMappingsArea);
        }

        if (!targetAssistantPanel) return;

        if (!model) {
            targetAssistantPanel.style.display = 'none';
            return;
        }

        try {
            const resp = await fetch(`/api/automation/introspection/?model=${encodeURIComponent(model)}`, {
                headers: { 'Accept': 'application/json' }
            });
            if (!resp.ok) return;
            const data = await resp.json();

            targetAssistantPanel.style.display = 'block';
            targetAssistantPanel.innerHTML = `
                <div class="auto-panel-header">
                    <span>📋 Destination Schema: <strong>${data.verbose_name}</strong> (<code>${data.model}</code>)</span>
                    <span style="font-size: 11px; font-weight: normal; color: #64748b;">Click field to map into JSON</span>
                </div>
                <div style="font-size: 11px; color: #475569; margin-bottom: 4px;">
                    <strong>Required Fields (*):</strong> ${data.required_fields.length > 0 ? data.required_fields.map(f => `<code style="color:#b91c1c; font-weight:bold;">${f}</code>`).join(', ') : '<em>None</em>'}
                </div>
                <div class="auto-pill-list" id="target_fields_container"></div>
                <div style="margin-top: 10px; border-top: 1px dashed #cbd5e1; padding-top: 8px;">
                    <span style="font-size: 11px; font-weight: 600; color: #334155; margin-right: 8px;">⚡ Trigger Context Variables:</span>
                    <span class="auto-tag-context" data-val="{{pk}}">{{pk}}</span>
                    <span class="auto-tag-context" data-val="{{username}}">{{username}}</span>
                    <span class="auto-tag-context" data-val="{{model}}">{{model}}</span>
                    <span class="auto-tag-context" data-val="{{now}}">{{now}}</span>
                </div>
            `;

            const pillContainer = targetAssistantPanel.querySelector('#target_fields_container');
            data.fields.forEach(f => {
                if (f.name === 'id') return;
                const pill = document.createElement('span');
                pill.className = `auto-field-pill ${f.required ? 'is-required' : ''}`;
                pill.title = `Type: ${f.type}${f.help_text ? ' — ' + f.help_text : ''}`;
                pill.innerHTML = `${f.name}${f.required ? ' *' : ''} <small style="opacity:0.7">(${f.type})</small>`;

                pill.addEventListener('click', () => {
                    appendFieldToMapping(f.name, f.type);
                });
                pillContainer.appendChild(pill);
            });

            // Bind context variable tags
            targetAssistantPanel.querySelectorAll('.auto-tag-context').forEach(tag => {
                tag.addEventListener('click', () => {
                    insertTextIntoFieldMappings(tag.getAttribute('data-val'));
                });
            });

        } catch (e) {
            console.warn('Failed to introspect target model:', e);
        }
    }

    function appendFieldToMapping(fieldName, fieldType) {
        if (!fieldMappingsArea) return;
        let mappings = {};
        try {
            const raw = fieldMappingsArea.value.trim();
            if (raw) {
                mappings = JSON.parse(raw);
            }
        } catch (e) {
            // Keep existing text if parse fails
        }

        if (!(fieldName in mappings)) {
            mappings[fieldName] = `{{${fieldName}}}`;
            fieldMappingsArea.value = JSON.stringify(mappings, null, 2);
        }
    }

    function insertTextIntoFieldMappings(text) {
        if (!fieldMappingsArea) return;
        const start = fieldMappingsArea.selectionStart;
        const end = fieldMappingsArea.selectionEnd;
        const val = fieldMappingsArea.value;
        fieldMappingsArea.value = val.substring(0, start) + text + val.substring(end);
        fieldMappingsArea.focus();
        fieldMappingsArea.selectionStart = fieldMappingsArea.selectionEnd = start + text.length;
    }

    targetModelSelect.addEventListener('change', introspectTargetModel);
    if (targetModelSelect.value) {
        introspectTargetModel();
    }

    // 4. VISUAL CONDITION RULES HELPER
    if (conditionRulesArea) {
        const rulesHelper = document.createElement('div');
        rulesHelper.style.margin = '6px 0 12px 0';
        rulesHelper.innerHTML = `
            <span style="font-size:11px; font-weight:600; color:#475569; margin-right:8px;">Quick Rule Presets:</span>
            <button type="button" class="auto-quick-btn" id="btn_add_status_rule">+ Status Equals</button>
            <button type="button" class="auto-quick-btn" id="btn_add_agent_rule">+ Is Agent True</button>
            <button type="button" class="auto-quick-btn" id="btn_add_cost_rule">+ Cost > Cap</button>
        `;
        conditionRulesArea.parentNode.insertBefore(rulesHelper, conditionRulesArea.nextSibling);

        function appendConditionRule(ruleObj) {
            let rules = [];
            try {
                const raw = conditionRulesArea.value.trim();
                if (raw) {
                    rules = JSON.parse(raw);
                    if (!Array.isArray(rules)) rules = [rules];
                }
            } catch (e) {
                rules = [];
            }
            rules.push(ruleObj);
            conditionRulesArea.value = JSON.stringify(rules, null, 2);
        }

        document.getElementById('btn_add_status_rule')?.addEventListener('click', () => {
            appendConditionRule({ field: 'status', operator: '==', value: 'completed' });
        });
        document.getElementById('btn_add_agent_rule')?.addEventListener('click', () => {
            appendConditionRule({ field: 'is_agent', operator: '==', value: true });
        });
        document.getElementById('btn_add_cost_rule')?.addEventListener('click', () => {
            appendConditionRule({ field: 'cost_usd', operator: '>', value: 5.0 });
        });
    }
});
