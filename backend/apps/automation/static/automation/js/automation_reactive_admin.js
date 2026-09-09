/**
 * Reactive Dynamic Admin UI for Centralized Automation Engine.
 *
 * Implements:
 * 1. Dynamic Section Toggling based on trigger_type (model_event vs time_based)
 * 2. AJAX Dynamic Field Introspection for trigger_model
 * 3. Interactive Condition Rules Table Builder with intelligent field discovery & date format helpers
 * 4. Interactive Schema Mapping Assistant for target_model on Action inlines and standalone actions
 */

document.addEventListener('DOMContentLoaded', function () {
    // Inject Custom Styles for Reactive Panels and Table Builder
    const style = document.createElement('style');
    style.textContent = `
        .auto-schema-panel {
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 12px 16px;
            margin: 10px 0;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
            font-size: 13px;
        }
        .auto-panel-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 8px;
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
            padding: 3px 8px;
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
            padding: 2px 7px;
            font-family: monospace;
            font-size: 11px;
            cursor: pointer;
            transition: all 0.15s ease;
            display: inline-block;
            margin: 2px 3px;
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

        /* Condition Rules Table Builder Styles */
        .auto-rules-container {
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 14px 16px;
            margin: 8px 0 16px 0;
            box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        }
        .auto-rules-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 10px;
        }
        .auto-rules-title {
            font-size: 13px;
            font-weight: 700;
            color: #1e293b;
            display: flex;
            align-items: center;
            gap: 6px;
        }
        .auto-rules-table {
            width: 100%;
            border-collapse: collapse;
            background: #ffffff;
            border: 1px solid #cbd5e1;
            border-radius: 6px;
            overflow: hidden;
            margin-bottom: 10px;
        }
        .auto-rules-table th {
            background: #f1f5f9;
            color: #475569;
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            padding: 8px 10px;
            border-bottom: 1px solid #cbd5e1;
            text-align: left;
        }
        .auto-rules-table td {
            padding: 8px 10px;
            border-bottom: 1px solid #e2e8f0;
            vertical-align: middle;
        }
        .auto-rules-table tr:last-child td {
            border-bottom: none;
        }
        .rule-field-select, .rule-operator-select {
            width: 100%;
            padding: 6px 8px;
            border: 1px solid #cbd5e1;
            border-radius: 4px;
            font-size: 12px;
            background: #ffffff;
            color: #1e293b;
        }
        .rule-value-input {
            width: 100%;
            padding: 6px 8px;
            border: 1px solid #cbd5e1;
            border-radius: 4px;
            font-size: 12px;
            box-sizing: border-box;
        }
        .rule-value-input:disabled {
            background: #f1f5f9;
            color: #94a3b8;
            cursor: not-allowed;
        }
        .rule-type-badge {
            display: inline-block;
            font-size: 10px;
            padding: 1px 5px;
            border-radius: 4px;
            background: #e0f2fe;
            color: #0369a1;
            margin-top: 3px;
            font-weight: 600;
        }
        .rule-del-btn {
            background: #fee2e2;
            border: 1px solid #fca5a5;
            color: #b91c1c;
            border-radius: 4px;
            width: 28px;
            height: 28px;
            font-size: 13px;
            font-weight: bold;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.15s ease;
        }
        .rule-del-btn:hover {
            background: #ef4444;
            color: #ffffff;
            border-color: #dc2626;
        }
        .auto-rules-btn-bar {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 12px;
        }
        .auto-add-btn {
            background: #0284c7;
            color: #ffffff;
            border: 1px solid #0369a1;
            padding: 5px 12px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.15s ease;
        }
        .auto-add-btn:hover {
            background: #0369a1;
        }
        .auto-clear-btn {
            background: #f8fafc;
            color: #64748b;
            border: 1px solid #cbd5e1;
            padding: 5px 10px;
            border-radius: 4px;
            font-size: 11px;
            cursor: pointer;
            transition: all 0.15s ease;
        }
        .auto-clear-btn:hover {
            background: #fee2e2;
            color: #b91c1c;
            border-color: #fca5a5;
        }
        .auto-empty-row {
            text-align: center;
            color: #94a3b8;
            font-size: 12px;
            padding: 16px !important;
            font-style: italic;
        }
        .auto-date-helper-card {
            background: #f0fdf4;
            border: 1px solid #bbf7d0;
            border-radius: 6px;
            padding: 10px 14px;
            font-size: 12px;
            color: #166534;
        }
        .auto-helper-title {
            font-weight: 700;
            margin-bottom: 6px;
            color: #14532d;
            display: flex;
            align-items: center;
            gap: 5px;
        }
        .auto-helper-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 8px 16px;
        }
        .auto-helper-item {
            font-size: 11px;
            line-height: 1.4;
        }
        .auto-helper-item code {
            background: #dcfce7;
            border: 1px solid #86efac;
            padding: 1px 5px;
            border-radius: 3px;
            font-weight: 600;
            color: #15803d;
        }
        .auto-helper-subtext {
            font-size: 10.5px;
            color: #15803d;
            opacity: 0.9;
            margin-top: 2px;
        }
    `;
    document.head.appendChild(style);

    // 1. TRIGGER FORM REACTIVITY & SECTION TOGGLING
    const triggerTypeSelect = document.querySelector('select[name="trigger_type"]');
    const triggerModelSelect = document.querySelector('select[name="trigger_model"]');
    const triggerFieldInput = document.querySelector('input[name="trigger_field"]');
    const conditionRulesArea = document.querySelector('textarea[name="condition_rules"]');

    let currentTriggerFields = [];

    if (triggerTypeSelect) {
        function getParentFieldset(element) {
            if (!element) return null;
            return element.closest('fieldset') || element.closest('.module');
        }

        const stateTransitionFieldset = getParentFieldset(triggerFieldInput);
        const celeryBeatFieldset = getParentFieldset(document.querySelector('select[name="schedule_unit"]'));

        function updateSectionVisibility() {
            const triggerType = triggerTypeSelect.value;
            if (triggerType === 'model_event') {
                if (celeryBeatFieldset) celeryBeatFieldset.style.display = 'none';
                if (stateTransitionFieldset) stateTransitionFieldset.style.display = '';
            } else if (triggerType === 'time_based') {
                if (celeryBeatFieldset) celeryBeatFieldset.style.display = '';
                if (stateTransitionFieldset) stateTransitionFieldset.style.display = 'none';
            } else {
                if (celeryBeatFieldset) celeryBeatFieldset.style.display = 'none';
                if (stateTransitionFieldset) stateTransitionFieldset.style.display = 'none';
            }
        }

        triggerTypeSelect.addEventListener('change', updateSectionVisibility);
        updateSectionVisibility();

        // 2. TRIGGER MODEL INTROSPECTION
        async function introspectTriggerModel() {
            const model = triggerModelSelect ? triggerModelSelect.value : '';
            if (!model) {
                currentTriggerFields = [];
                updateAllFieldDropdowns();
                return;
            }

            try {
                const resp = await fetch(`/api/automation/introspection/?model=${encodeURIComponent(model)}`, {
                    headers: { 'Accept': 'application/json' }
                });
                if (!resp.ok) return;
                const data = await resp.json();
                currentTriggerFields = data.fields || [];

                // Trigger Field datalist
                if (triggerFieldInput) {
                    let datalist = document.getElementById('trigger_fields_datalist');
                    if (!datalist) {
                        datalist = document.createElement('datalist');
                        datalist.id = 'trigger_fields_datalist';
                        document.body.appendChild(datalist);
                        triggerFieldInput.setAttribute('list', 'trigger_fields_datalist');
                    }
                    datalist.innerHTML = '';
                    currentTriggerFields.forEach(f => {
                        const opt = document.createElement('option');
                        opt.value = f.name;
                        opt.label = `${f.name} (${f.type})`;
                        datalist.appendChild(opt);
                    });
                }

                // Trigger Model badge
                let badge = document.getElementById('trigger_model_badge');
                if (!badge) {
                    badge = document.createElement('span');
                    badge.id = 'trigger_model_badge';
                    badge.className = 'auto-badge-info';
                    triggerModelSelect.parentNode.appendChild(badge);
                }
                badge.textContent = `✓ ${data.verbose_name} (${data.fields.length} fields)`;

                // Update Condition Rules Table field dropdowns
                updateAllFieldDropdowns();
            } catch (e) {
                console.warn('Failed to introspect trigger model:', e);
            }
        }

        if (triggerModelSelect) {
            triggerModelSelect.addEventListener('change', introspectTriggerModel);
            if (triggerModelSelect.value) {
                introspectTriggerModel();
            }
        }

        // 3. INTERACTIVE CONDITION RULES TABLE BUILDER
        if (conditionRulesArea) {
            // Hide the raw JSON textarea from view but keep it for form submission
            conditionRulesArea.style.display = 'none';

            // Create Visual Table Container
            const tableContainer = document.createElement('div');
            tableContainer.className = 'auto-rules-container';
            tableContainer.id = 'condition_rules_table_container';

            tableContainer.innerHTML = `
                <div class="auto-rules-header">
                    <div class="auto-rules-title">
                        <span>🎯 Visual Condition Rules</span>
                        <small style="color:#64748b; font-weight:normal; margin-left:8px;">All condition rules must match (AND) to activate execution.</small>
                    </div>
                </div>

                <table class="auto-rules-table" id="condition_rules_table">
                    <thead>
                        <tr>
                            <th style="width: 32%;">Field (Attribute)</th>
                            <th style="width: 25%;">Operator</th>
                            <th style="width: 37%;">Expected Value</th>
                            <th style="width: 6%; text-align: center;">Actions</th>
                        </tr>
                    </thead>
                    <tbody id="condition_rules_tbody">
                        <tr class="auto-empty-row"><td colspan="4">No condition rules added yet. Click "+ Add Condition" below.</td></tr>
                    </tbody>
                </table>

                <div class="auto-rules-btn-bar">
                    <button type="button" class="auto-add-btn" id="btn_add_table_rule">+ Add Condition</button>
                    <button type="button" class="auto-clear-btn" id="btn_clear_table_rules">🗑️ Clear All</button>
                </div>

                <div class="auto-date-helper-card">
                    <div class="auto-helper-title">💡 Value Formatting & Database Type Guide:</div>
                    <div class="auto-helper-grid">
                        <div class="auto-helper-item">
                            <strong>📅 Dates (Django / Database Standard):</strong>
                            <div>Use ISO format: <code>YYYY-MM-DD</code></div>
                            <div class="auto-helper-subtext">Must start with 4-digit year, then month, then day. Example: <code>2026-09-09</code>. Works with <code>&gt;</code>, <code>&lt;</code>, <code>&gt;=</code>, <code>&lt;=</code>, <code>==</code>.</div>
                        </div>
                        <div class="auto-helper-item">
                            <strong>⏱️ Timestamps (DateTimes):</strong>
                            <div>Format: <code>YYYY-MM-DD HH:MM:SS</code></div>
                            <div class="auto-helper-subtext">Example: <code>2026-09-09 14:30:00</code>. Supports chronological comparisons.</div>
                        </div>
                        <div class="auto-helper-item">
                            <strong>🔢 Numbers & Decimals:</strong>
                            <div>Format: <code>10</code>, <code>3.75</code>, <code>-5.0</code></div>
                            <div class="auto-helper-subtext">Supports arithmetic comparisons: <code>&gt;</code>, <code>&lt;</code>, <code>&gt;=</code>, <code>&lt;=</code>.</div>
                        </div>
                        <div class="auto-helper-item">
                            <strong>🔤 Booleans & Choices:</strong>
                            <div>Use <code>true</code> / <code>false</code> or exact choice values like <code>completed</code>.</div>
                        </div>
                    </div>
                </div>
            `;

            conditionRulesArea.parentNode.insertBefore(tableContainer, conditionRulesArea);

            const tbody = tableContainer.querySelector('#condition_rules_tbody');
            const addBtn = tableContainer.querySelector('#btn_add_table_rule');
            const clearBtn = tableContainer.querySelector('#btn_clear_table_rules');

            const OPERATORS = [
                { val: '==', label: '== (Equals)' },
                { val: '!=', label: '!= (Does Not Equal)' },
                { val: '>', label: '> (Greater Than / After)' },
                { val: '>=', label: '>= (Greater or Equal / On or After)' },
                { val: '<', label: '< (Less Than / Before)' },
                { val: '<=', label: '<= (Less or Equal / On or Before)' },
                { val: 'contains', label: 'contains (Contains String)' },
                { val: 'not_contains', label: 'not_contains (Does Not Contain)' },
                { val: 'in', label: 'in (In List: val1, val2)' },
                { val: 'not_in', label: 'not_in (Not in List)' },
                { val: 'is_empty', label: 'is_empty (Is Null / Empty)' },
                { val: 'is_not_empty', label: 'is_not_empty (Is Not Null)' },
            ];

            function createRow(initialField = '', initialOp = '==', initialVal = '') {
                // Remove empty row message if present
                const emptyRow = tbody.querySelector('.auto-empty-row');
                if (emptyRow) emptyRow.remove();

                const tr = document.createElement('tr');

                // 1. Field Cell
                const tdField = document.createElement('td');
                const selectField = document.createElement('select');
                selectField.className = 'rule-field-select';
                populateFieldOptions(selectField, initialField);

                const typeBadge = document.createElement('div');
                typeBadge.className = 'rule-type-badge';
                updateTypeBadge(selectField, typeBadge);

                selectField.addEventListener('change', () => {
                    updateTypeBadge(selectField, typeBadge);
                    updateValueInputHints(selectField, selectOp, inputVal, valHint);
                    serializeTableToJSON();
                });

                tdField.appendChild(selectField);
                tdField.appendChild(typeBadge);
                tr.appendChild(tdField);

                // 2. Operator Cell
                const tdOp = document.createElement('td');
                const selectOp = document.createElement('select');
                selectOp.className = 'rule-operator-select';
                OPERATORS.forEach(op => {
                    const opt = document.createElement('option');
                    opt.value = op.val;
                    opt.textContent = op.label;
                    if (op.val === initialOp) opt.selected = true;
                    selectOp.appendChild(opt);
                });

                selectOp.addEventListener('change', () => {
                    updateValueInputHints(selectField, selectOp, inputVal, valHint);
                    serializeTableToJSON();
                });

                tdOp.appendChild(selectOp);
                tr.appendChild(tdOp);

                // 3. Expected Value Cell
                const tdVal = document.createElement('td');
                const inputVal = document.createElement('input');
                inputVal.className = 'rule-value-input';
                inputVal.value = (initialVal !== undefined && initialVal !== null) ? String(initialVal) : '';

                const valHint = document.createElement('small');
                valHint.className = 'auto-helper-subtext';
                valHint.style.display = 'block';

                inputVal.addEventListener('input', serializeTableToJSON);

                tdVal.appendChild(inputVal);
                tdVal.appendChild(valHint);
                tr.appendChild(tdVal);

                // 4. Action Cell (Delete)
                const tdAction = document.createElement('td');
                tdAction.style.textAlign = 'center';
                const delBtn = document.createElement('button');
                delBtn.type = 'button';
                delBtn.className = 'rule-del-btn';
                delBtn.innerHTML = '✕';
                delBtn.title = 'Remove Condition Rule';
                delBtn.addEventListener('click', () => {
                    tr.remove();
                    if (tbody.querySelectorAll('tr').length === 0) {
                        tbody.innerHTML = '<tr class="auto-empty-row"><td colspan="4">No condition rules added yet. Click "+ Add Condition" below.</td></tr>';
                    }
                    serializeTableToJSON();
                });
                tdAction.appendChild(delBtn);
                tr.appendChild(tdAction);

                updateValueInputHints(selectField, selectOp, inputVal, valHint);

                return tr;
            }

            function populateFieldOptions(selectEl, selectedVal) {
                selectEl.innerHTML = '';
                const defaultOpt = document.createElement('option');
                defaultOpt.value = '';
                defaultOpt.textContent = '-- Select Field --';
                selectEl.appendChild(defaultOpt);

                let matched = false;
                currentTriggerFields.forEach(f => {
                    const opt = document.createElement('option');
                    opt.value = f.name;
                    opt.textContent = `${f.name} (${f.verbose_name || f.type})`;
                    opt.dataset.type = f.type || '';
                    if (f.choices && f.choices.length) {
                        opt.dataset.choices = JSON.stringify(f.choices);
                    }
                    if (f.name === selectedVal) {
                        opt.selected = true;
                        matched = true;
                    }
                    selectEl.appendChild(opt);
                });

                // If selectedVal is custom or not yet introspected
                if (selectedVal && !matched) {
                    const customOpt = document.createElement('option');
                    customOpt.value = selectedVal;
                    customOpt.textContent = `${selectedVal} (custom)`;
                    customOpt.selected = true;
                    selectEl.appendChild(customOpt);
                }
            }

            function updateTypeBadge(selectField, badgeEl) {
                const selectedOpt = selectField.options[selectField.selectedIndex];
                const type = selectedOpt ? selectedOpt.dataset.type : '';
                if (type) {
                    badgeEl.style.display = 'inline-block';
                    badgeEl.textContent = type;
                } else {
                    badgeEl.style.display = 'none';
                }
            }

            function updateValueInputHints(selectField, selectOp, inputVal, hintEl) {
                const op = selectOp.value;
                const selectedOpt = selectField.options[selectField.selectedIndex];
                const type = selectedOpt ? selectedOpt.dataset.type : '';

                if (op === 'is_empty' || op === 'is_not_empty') {
                    inputVal.disabled = true;
                    inputVal.placeholder = '(No value required for this operator)';
                    hintEl.textContent = '';
                    return;
                }

                inputVal.disabled = false;

                if (type === 'DateField') {
                    inputVal.placeholder = 'YYYY-MM-DD (e.g. 2026-09-09)';
                    hintEl.innerHTML = '📅 Django Date format: <code>YYYY-MM-DD</code> (Year-Month-Day)';
                } else if (type === 'DateTimeField') {
                    inputVal.placeholder = 'YYYY-MM-DD HH:MM:SS';
                    hintEl.innerHTML = '⏱️ Timestamp format: <code>YYYY-MM-DD HH:MM:SS</code>';
                } else if (type === 'BooleanField') {
                    inputVal.placeholder = 'true or false';
                    hintEl.innerHTML = 'Use <code>true</code> or <code>false</code>';
                } else if (type === 'IntegerField' || type === 'DecimalField' || type === 'FloatField') {
                    inputVal.placeholder = 'e.g. 10 or 3.75';
                    hintEl.innerHTML = '🔢 Numeric comparison';
                } else {
                    inputVal.placeholder = 'Expected value or {{variable}}';
                    hintEl.innerHTML = '';
                }
            }

            function serializeTableToJSON() {
                const rows = tbody.querySelectorAll('tr:not(.auto-empty-row)');
                const rules = [];

                rows.forEach(r => {
                    const field = r.querySelector('.rule-field-select').value.trim();
                    const op = r.querySelector('.rule-operator-select').value;
                    const rawVal = r.querySelector('.rule-value-input').value.trim();

                    if (!field) return;

                    let finalVal = rawVal;
                    if (op === 'is_empty' || op === 'is_not_empty') {
                        finalVal = '';
                    } else if (rawVal.toLowerCase() === 'true') {
                        finalVal = true;
                    } else if (rawVal.toLowerCase() === 'false') {
                        finalVal = false;
                    } else if (/^-?\d+(\.\d+)?$/.test(rawVal) && !/^\d{4}-\d{2}-\d{2}$/.test(rawVal)) {
                        // Numeric value (not a date string like 2026-09-09)
                        finalVal = rawVal.includes('.') ? parseFloat(rawVal) : parseInt(rawVal, 10);
                    }

                    rules.push({
                        field: field,
                        operator: op,
                        value: finalVal
                    });
                });

                conditionRulesArea.value = JSON.stringify(rules, null, 2);
            }

            function deserializeJSONToTable() {
                tbody.innerHTML = '';
                let existingRules = [];
                try {
                    const raw = conditionRulesArea.value.trim();
                    if (raw) {
                        existingRules = JSON.parse(raw);
                        if (!Array.isArray(existingRules)) existingRules = [existingRules];
                    }
                } catch (e) {
                    existingRules = [];
                }

                if (existingRules.length === 0) {
                    tbody.innerHTML = '<tr class="auto-empty-row"><td colspan="4">No condition rules added yet. Click "+ Add Condition" below.</td></tr>';
                    return;
                }

                existingRules.forEach(r => {
                    if (typeof r !== 'object' || !r) return;
                    const tr = createRow(r.field || '', r.operator || '==', r.value !== undefined ? r.value : '');
                    tbody.appendChild(tr);
                });
            }

            function updateAllFieldDropdowns() {
                const rows = tbody.querySelectorAll('tr:not(.auto-empty-row)');
                rows.forEach(r => {
                    const select = r.querySelector('.rule-field-select');
                    const currentVal = select.value;
                    const badge = r.querySelector('.rule-type-badge');
                    const op = r.querySelector('.rule-operator-select');
                    const valInput = r.querySelector('.rule-value-input');
                    const hint = r.querySelector('.auto-helper-subtext');

                    populateFieldOptions(select, currentVal);
                    updateTypeBadge(select, badge);
                    updateValueInputHints(select, op, valInput, hint);
                });
            }

            addBtn.addEventListener('click', () => {
                const defaultField = currentTriggerFields.length > 0 ? currentTriggerFields[0].name : '';
                const tr = createRow(defaultField, '==', '');
                tbody.appendChild(tr);
                serializeTableToJSON();
            });

            clearBtn.addEventListener('click', () => {
                tbody.innerHTML = '<tr class="auto-empty-row"><td colspan="4">No condition rules added yet. Click "+ Add Condition" below.</td></tr>';
                serializeTableToJSON();
            });

            // Initialize table rows from existing JSON
            deserializeJSONToTable();
        }
    }

    // 4. TARGET MODEL INTROSPECTION & MAPPING ASSISTANT (ACTIONS & INLINES)
    function setupActionMappingAssistant(container) {
        const targetModelSelects = container.querySelectorAll('select[name$="target_model"]');

        targetModelSelects.forEach(select => {
            if (select.dataset.autoIntrospectBound) return;
            select.dataset.autoIntrospectBound = "true";

            const parentRow = select.closest('.inline-related') || select.closest('fieldset') || select.closest('form');
            if (!parentRow) return;

            const fieldMappingsArea = parentRow.querySelector('textarea[name$="field_mappings"]');
            if (!fieldMappingsArea) return;

            let assistantPanel = null;

            async function introspectTarget() {
                const model = select.value;
                if (!assistantPanel) {
                    assistantPanel = document.createElement('div');
                    assistantPanel.className = 'auto-schema-panel';
                    fieldMappingsArea.parentNode.insertBefore(assistantPanel, fieldMappingsArea);
                }

                if (!model) {
                    assistantPanel.style.display = 'none';
                    return;
                }

                try {
                    const resp = await fetch(`/api/automation/introspection/?model=${encodeURIComponent(model)}`, {
                        headers: { 'Accept': 'application/json' }
                    });
                    if (!resp.ok) return;
                    const data = await resp.json();

                    assistantPanel.style.display = 'block';
                    assistantPanel.innerHTML = `
                        <div class="auto-panel-header">
                            <span>📋 Destination Schema: <strong>${data.verbose_name}</strong> (<code>${data.model}</code>)</span>
                            <span style="font-size: 11px; font-weight: normal; color: #64748b;">Click field to insert into JSON</span>
                        </div>
                        <div style="font-size: 11px; color: #475569; margin-bottom: 4px;">
                            <strong>Required Fields (*):</strong> ${data.required_fields.length > 0 ? data.required_fields.map(f => `<code style="color:#b91c1c; font-weight:bold;">${f}</code>`).join(', ') : '<em>None</em>'}
                        </div>
                        <div class="auto-pill-list" id="target_fields_container_${data.model.replace('.', '_')}"></div>
                        <div style="margin-top: 8px; border-top: 1px dashed #cbd5e1; padding-top: 6px;">
                            <span style="font-size: 11px; font-weight: 600; color: #334155; margin-right: 6px;">⚡ Context Variables:</span>
                            <span class="auto-tag-context" data-val="{{pk}}">{{pk}}</span>
                            <span class="auto-tag-context" data-val="{{username}}">{{username}}</span>
                            <span class="auto-tag-context" data-val="{{model}}">{{model}}</span>
                            <span class="auto-tag-context" data-val="{{now}}">{{now}}</span>
                        </div>
                    `;

                    const pillContainer = assistantPanel.querySelector(`#target_fields_container_${data.model.replace('.', '_')}`);
                    (data.fields || []).forEach(f => {
                        if (f.name === 'id') return;
                        const pill = document.createElement('span');
                        pill.className = `auto-field-pill ${f.required ? 'is-required' : ''}`;
                        pill.title = `Type: ${f.type}${f.help_text ? ' — ' + f.help_text : ''}`;
                        pill.innerHTML = `${f.name}${f.required ? ' *' : ''} <small style="opacity:0.7">(${f.type})</small>`;

                        pill.addEventListener('click', () => {
                            let mappings = {};
                            try {
                                const raw = fieldMappingsArea.value.trim();
                                if (raw) mappings = JSON.parse(raw);
                            } catch (e) {}

                            if (!(f.name in mappings)) {
                                mappings[f.name] = `{{${f.name}}}`;
                                fieldMappingsArea.value = JSON.stringify(mappings, null, 2);
                            }
                        });
                        pillContainer.appendChild(pill);
                    });

                    assistantPanel.querySelectorAll('.auto-tag-context').forEach(tag => {
                        tag.addEventListener('click', () => {
                            const text = tag.getAttribute('data-val');
                            const start = fieldMappingsArea.selectionStart;
                            const end = fieldMappingsArea.selectionEnd;
                            const val = fieldMappingsArea.value;
                            fieldMappingsArea.value = val.substring(0, start) + text + val.substring(end);
                            fieldMappingsArea.focus();
                            fieldMappingsArea.selectionStart = fieldMappingsArea.selectionEnd = start + text.length;
                        });
                    });

                } catch (e) {
                    console.warn('Failed to introspect target model for action:', e);
                }
            }

            select.addEventListener('change', introspectTarget);
            if (select.value) {
                introspectTarget();
            }
        });
    }

    setupActionMappingAssistant(document);

    const observer = new MutationObserver((mutations) => {
        mutations.forEach(mutation => {
            if (mutation.addedNodes.length > 0) {
                setupActionMappingAssistant(document);
            }
        });
    });
    observer.observe(document.body, { childList: true, subtree: true });
});
