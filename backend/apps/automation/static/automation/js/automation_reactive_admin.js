/**
 * Reactive Dynamic Admin UI for Centralized Automation Engine.
 *
 * Implements:
 * 1. Dynamic Section Toggling based on trigger_type (model_event vs time_based)
 * 2. AJAX Dynamic Field Introspection for trigger_model
 * 3. Unified Filter Conditions Builder (Option A: Visual Group Blocks with Parentheses Grouping & Date Helpers)
 * 4. Interactive Schema Mapping Assistant for target_model on Action inlines and standalone actions
 */

document.addEventListener('DOMContentLoaded', function () {
    // Inject Custom Styles for Reactive Panels and Group Builder
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
        .auto-preset-list {
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            margin: 6px 0 10px 0;
        }
        .auto-preset-btn {
            background: #ffffff;
            border: 1px solid #93c5fd;
            color: #1d4ed8;
            border-radius: 6px;
            padding: 4px 10px;
            font-size: 11.5px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.15s ease;
            box-shadow: 0 1px 2px rgba(0,0,0,0.03);
            display: inline-flex;
            align-items: center;
            gap: 4px;
        }
        .auto-preset-btn:hover {
            background: #eff6ff;
            border-color: #3b82f6;
            color: #1e40af;
            transform: translateY(-1px);
        }
        .auto-schema-hint {
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 6px;
            padding: 8px 10px;
            font-size: 11px;
            color: #475569;
            margin-top: 6px;
        }
        .auto-schema-hint code {
            font-weight: 600;
            color: #0f172a;
        }

        /* Group Builder Component Styles (Option A) */
        .auto-builder-card {
            background: #f8fafc;
            border: 1px solid #cbd5e1;
            border-radius: 8px;
            padding: 16px 18px;
            margin: 8px 0 16px 0;
            box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        }
        .auto-group-block {
            background: #ffffff;
            border: 1px solid #cbd5e1;
            border-radius: 6px;
            padding: 12px 14px;
            margin: 8px 0;
            box-shadow: 0 1px 2px rgba(0,0,0,0.03);
            transition: all 0.15s ease;
        }
        .auto-group-block.is-nested {
            background: #fcfdfe;
            border-left: 4px solid #0284c7;
            margin-left: 18px;
            margin-top: 8px;
            margin-bottom: 8px;
        }
        .auto-group-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 10px;
            padding-bottom: 6px;
            border-bottom: 1px solid #f1f5f9;
            gap: 8px;
        }
        .auto-group-title {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 12px;
            font-weight: 600;
            color: #334155;
        }
        .auto-group-combinator {
            padding: 4px 8px;
            font-weight: 700;
            font-size: 11px;
            border-radius: 4px;
            border: 1px solid #0284c7;
            background: #f0f9ff;
            color: #0369a1;
            cursor: pointer;
        }
        .auto-group-rules-container {
            display: flex;
            flex-direction: column;
            gap: 6px;
        }
        .auto-rule-row {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 6px 0;
            border-bottom: 1px dashed #e2e8f0;
        }
        .auto-rule-row:last-child {
            border-bottom: none;
        }
        .rule-field-cell {
            flex: 3;
            min-width: 140px;
        }
        .rule-op-cell {
            flex: 2;
            min-width: 130px;
        }
        .rule-val-cell {
            flex: 4;
            min-width: 160px;
        }
        .rule-act-cell {
            width: 32px;
            text-align: center;
        }
        .rule-field-select, .rule-operator-select {
            width: 100%;
            padding: 6px 8px;
            border: 1px solid #cbd5e1;
            border-radius: 4px;
            font-size: 12px;
            background: #ffffff;
            color: #1e293b;
            box-sizing: border-box;
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
            width: 26px;
            height: 26px;
            font-size: 12px;
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
        .auto-group-footer {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-top: 10px;
            padding-top: 6px;
            border-top: 1px solid #f1f5f9;
        }
        .auto-btn-add-rule {
            background: #0284c7;
            color: #ffffff;
            border: 1px solid #0369a1;
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.15s ease;
        }
        .auto-btn-add-rule:hover {
            background: #0369a1;
        }
        .auto-btn-add-group {
            background: #f8fafc;
            color: #334155;
            border: 1px solid #cbd5e1;
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.15s ease;
        }
        .auto-btn-add-group:hover {
            background: #e2e8f0;
            color: #0f172a;
        }
        .auto-btn-del-group {
            background: #fee2e2;
            color: #b91c1c;
            border: 1px solid #fca5a5;
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.15s ease;
        }
        .auto-btn-del-group:hover {
            background: #ef4444;
            color: #ffffff;
        }
        .auto-builder-btn-bar {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 12px;
        }
        .auto-date-helper-card {
            background: #f0fdf4;
            border: 1px solid #bbf7d0;
            border-radius: 6px;
            padding: 10px 14px;
            font-size: 12px;
            color: #166534;
            margin-top: 12px;
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
        .auto-empty-group-text {
            color: #94a3b8;
            font-size: 11px;
            font-style: italic;
            padding: 6px 0;
        }
    `;
    document.head.appendChild(style);

    // 1. TRIGGER FORM REACTIVITY & SECTION TOGGLING
    const triggerTypeSelect = document.querySelector('select[name="trigger_type"]');
    const triggerModelSelect = document.querySelector('select[name="trigger_model"]');
    const triggerFieldInput = document.querySelector('input[name="trigger_field"]');
    const filterConditionsArea = document.querySelector('textarea[name="filter_conditions"]');
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

                updateAllFieldDropdowns();
                if (typeof activeParamsAssistants !== 'undefined') {
                    activeParamsAssistants.forEach(fn => {
                        try { fn(); } catch (err) {}
                    });
                }
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

        // 3. OPTION A: VISUAL GROUP BUILDER (BOOLEAN TREE AND/OR WITH PARENTHESES)
        const targetArea = filterConditionsArea || conditionRulesArea;

        if (targetArea) {
            // Hide raw textareas from view
            if (filterConditionsArea) filterConditionsArea.style.display = 'none';
            if (conditionRulesArea) conditionRulesArea.style.display = 'none';

            // Also hide original condition_rules field row container if both exist
            if (conditionRulesArea && filterConditionsArea) {
                const crRow = conditionRulesArea.closest('.form-row') || conditionRulesArea.closest('.field-condition_rules');
                if (crRow) crRow.style.display = 'none';
            }

            const builderCard = document.createElement('div');
            builderCard.className = 'auto-builder-card';
            builderCard.id = 'unified_filter_group_builder';

            builderCard.innerHTML = `
                <div class="auto-builder-btn-bar">
                    <div style="font-weight:700; font-size:13px; color:#1e293b; display:flex; align-items:center; gap:6px;">
                        <span>🎯 Trigger Filter Conditions</span>
                        <small style="color:#64748b; font-weight:normal;">(Boolean Rules with AND, OR & Groups)</small>
                    </div>
                    <button type="button" class="auto-btn-del-group" id="btn_builder_reset_all">🗑️ Reset All</button>
                </div>

                <div id="root_group_container"></div>

                <div class="auto-date-helper-card">
                    <div class="auto-helper-title">💡 Value Formatting & Database Type Guide:</div>
                    <div class="auto-helper-grid">
                        <div class="auto-helper-item">
                            <strong>📅 Dates (Django Standard):</strong>
                            <div>Format: <code>YYYY-MM-DD</code> (e.g. <code>2026-09-09</code>)</div>
                            <div class="auto-helper-subtext">Must start with 4-digit year, month, day. Works with <code>&gt;</code>, <code>&lt;</code>, <code>&gt;=</code>, <code>&lt;=</code>, <code>==</code>.</div>
                        </div>
                        <div class="auto-helper-item">
                            <strong>⏱️ Timestamps (DateTimes):</strong>
                            <div>Format: <code>YYYY-MM-DD HH:MM:SS</code></div>
                            <div class="auto-helper-subtext">Supports chronological comparisons.</div>
                        </div>
                        <div class="auto-helper-item">
                            <strong>🔢 Numbers & Decimals:</strong>
                            <div>Format: <code>10</code>, <code>3.75</code>, <code>-5.0</code></div>
                            <div class="auto-helper-subtext">Supports numeric comparisons: <code>&gt;</code>, <code>&lt;</code>, <code>&gt;=</code>, <code>&lt;=</code>.</div>
                        </div>
                        <div class="auto-helper-item">
                            <strong>🔤 Booleans & Choices:</strong>
                            <div>Use <code>true</code> / <code>false</code> or choice values like <code>completed</code>.</div>
                        </div>
                    </div>
                </div>
            `;

            targetArea.parentNode.insertBefore(builderCard, targetArea);

            const rootContainer = builderCard.querySelector('#root_group_container');
            const resetBtn = builderCard.querySelector('#btn_builder_reset_all');

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

            // Renders an individual Condition Rule Row
            function createRuleRow(initialField = '', initialOp = '==', initialVal = '') {
                const row = document.createElement('div');
                row.className = 'auto-rule-row';

                // 1. Field Selector
                const cellField = document.createElement('div');
                cellField.className = 'rule-field-cell';
                const selectField = document.createElement('select');
                selectField.className = 'rule-field-select';
                populateFieldOptions(selectField, initialField);

                const typeBadge = document.createElement('div');
                typeBadge.className = 'rule-type-badge';
                updateTypeBadge(selectField, typeBadge);

                selectField.addEventListener('change', () => {
                    updateTypeBadge(selectField, typeBadge);
                    updateValueInputHints(selectField, selectOp, inputVal, valHint);
                    serializeTreeToJSON();
                });

                cellField.appendChild(selectField);
                cellField.appendChild(typeBadge);
                row.appendChild(cellField);

                // 2. Operator Selector
                const cellOp = document.createElement('div');
                cellOp.className = 'rule-op-cell';
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
                    serializeTreeToJSON();
                });

                cellOp.appendChild(selectOp);
                row.appendChild(cellOp);

                // 3. Expected Value Input
                const cellVal = document.createElement('div');
                cellVal.className = 'rule-val-cell';
                const inputVal = document.createElement('input');
                inputVal.className = 'rule-value-input';
                inputVal.value = (initialVal !== undefined && initialVal !== null) ? String(initialVal) : '';

                const valHint = document.createElement('small');
                valHint.className = 'auto-helper-subtext';
                valHint.style.display = 'block';

                inputVal.addEventListener('input', serializeTreeToJSON);

                cellVal.appendChild(inputVal);
                cellVal.appendChild(valHint);
                row.appendChild(cellVal);

                // 4. Action (Delete Row)
                const cellAct = document.createElement('div');
                cellAct.className = 'rule-act-cell';
                const delBtn = document.createElement('button');
                delBtn.type = 'button';
                delBtn.className = 'rule-del-btn';
                delBtn.innerHTML = '✕';
                delBtn.title = 'Remove Condition';
                delBtn.addEventListener('click', () => {
                    const parentContainer = row.parentNode;
                    row.remove();
                    checkEmptyContainer(parentContainer);
                    serializeTreeToJSON();
                });
                cellAct.appendChild(delBtn);
                row.appendChild(cellAct);

                updateValueInputHints(selectField, selectOp, inputVal, valHint);
                return row;
            }

            // Renders a Group Block (Can contain rules and nested group blocks)
            function createGroupBlock(isNested = false, combinator = 'AND') {
                const group = document.createElement('div');
                group.className = `auto-group-block ${isNested ? 'is-nested' : 'is-root'}`;

                // Header
                const header = document.createElement('div');
                header.className = 'auto-group-header';

                const title = document.createElement('div');
                title.className = 'auto-group-title';

                const labelSpan = document.createElement('span');
                labelSpan.textContent = isNested ? 'Match' : 'Match for Trigger:';

                const selectComb = document.createElement('select');
                selectComb.className = 'auto-group-combinator';
                selectComb.innerHTML = `
                    <option value="AND" ${combinator === 'AND' ? 'selected' : ''}>ALL of the following (AND)</option>
                    <option value="OR" ${combinator === 'OR' ? 'selected' : ''}>ANY of the following (OR)</option>
                `;
                selectComb.addEventListener('change', serializeTreeToJSON);

                const groupBadge = document.createElement('span');
                groupBadge.style.fontSize = '11px';
                groupBadge.style.color = '#64748b';
                groupBadge.textContent = isNested ? '── Sub-Group ( ... )' : '';

                title.appendChild(labelSpan);
                title.appendChild(selectComb);
                title.appendChild(groupBadge);
                header.appendChild(title);

                // Delete Group Button (if nested)
                if (isNested) {
                    const delGroupBtn = document.createElement('button');
                    delGroupBtn.type = 'button';
                    delGroupBtn.className = 'auto-btn-del-group';
                    delGroupBtn.innerHTML = '✕ Delete Group';
                    delGroupBtn.addEventListener('click', () => {
                        const parentContainer = group.parentNode;
                        group.remove();
                        checkEmptyContainer(parentContainer);
                        serializeTreeToJSON();
                    });
                    header.appendChild(delGroupBtn);
                }

                group.appendChild(header);

                // Rules Container
                const rulesContainer = document.createElement('div');
                rulesContainer.className = 'auto-group-rules-container';
                group.appendChild(rulesContainer);

                // Footer Bar
                const footer = document.createElement('div');
                footer.className = 'auto-group-footer';

                const addRuleBtn = document.createElement('button');
                addRuleBtn.type = 'button';
                addRuleBtn.className = 'auto-btn-add-rule';
                addRuleBtn.textContent = '+ Add Condition';
                addRuleBtn.addEventListener('click', () => {
                    const emptyMsg = rulesContainer.querySelector('.auto-empty-group-text');
                    if (emptyMsg) emptyMsg.remove();

                    const defaultField = currentTriggerFields.length > 0 ? currentTriggerFields[0].name : '';
                    const ruleRow = createRuleRow(defaultField, '==', '');
                    rulesContainer.appendChild(ruleRow);
                    serializeTreeToJSON();
                });

                const addGroupBtn = document.createElement('button');
                addGroupBtn.type = 'button';
                addGroupBtn.className = 'auto-btn-add-group';
                addGroupBtn.textContent = '+ Add Group (...)';
                addGroupBtn.addEventListener('click', () => {
                    const emptyMsg = rulesContainer.querySelector('.auto-empty-group-text');
                    if (emptyMsg) emptyMsg.remove();

                    const subGroup = createGroupBlock(true, 'OR');
                    const defaultField = currentTriggerFields.length > 0 ? currentTriggerFields[0].name : '';
                    subGroup.querySelector('.auto-group-rules-container').appendChild(createRuleRow(defaultField, '==', ''));
                    rulesContainer.appendChild(subGroup);
                    serializeTreeToJSON();
                });

                footer.appendChild(addRuleBtn);
                footer.appendChild(addGroupBtn);
                group.appendChild(footer);

                return group;
            }

            function checkEmptyContainer(container) {
                if (!container) return;
                const hasChildren = container.querySelector('.auto-rule-row') || container.querySelector('.auto-group-block');
                if (!hasChildren && !container.querySelector('.auto-empty-group-text')) {
                    const empty = document.createElement('div');
                    empty.className = 'auto-empty-group-text';
                    empty.textContent = 'No conditions in this group. Click "+ Add Condition" below.';
                    container.appendChild(empty);
                }
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
                    inputVal.placeholder = '(No value required)';
                    hintEl.textContent = '';
                    return;
                }

                inputVal.disabled = false;

                if (type === 'DateField') {
                    inputVal.placeholder = 'YYYY-MM-DD (e.g. 2026-09-09)';
                    hintEl.innerHTML = '📅 Format: <code>YYYY-MM-DD</code> (Year-Month-Day)';
                } else if (type === 'DateTimeField') {
                    inputVal.placeholder = 'YYYY-MM-DD HH:MM:SS';
                    hintEl.innerHTML = '⏱️ Timestamp: <code>YYYY-MM-DD HH:MM:SS</code>';
                } else if (type === 'BooleanField') {
                    inputVal.placeholder = 'true or false';
                    hintEl.innerHTML = 'Use <code>true</code> or <code>false</code>';
                } else if (type === 'IntegerField' || type === 'DecimalField' || type === 'FloatField') {
                    inputVal.placeholder = 'e.g. 10 or 3.75';
                    hintEl.innerHTML = '🔢 Numeric value';
                } else {
                    inputVal.placeholder = 'Value or {{variable}}';
                    hintEl.innerHTML = '';
                }
            }

            // Serializes the DOM Group Tree into Boolean JSON
            function serializeGroupElement(groupEl) {
                const combSelect = groupEl.querySelector(':scope > .auto-group-header .auto-group-combinator');
                const combinator = combSelect ? combSelect.value : 'AND';
                const rulesContainer = groupEl.querySelector(':scope > .auto-group-rules-container');
                const rules = [];

                if (rulesContainer) {
                    Array.from(rulesContainer.children).forEach(child => {
                        if (child.classList.contains('auto-rule-row')) {
                            const field = child.querySelector('.rule-field-select').value.trim();
                            const op = child.querySelector('.rule-operator-select').value;
                            const rawVal = child.querySelector('.rule-value-input').value.trim();

                            if (!field) return;

                            let finalVal = rawVal;
                            if (op === 'is_empty' || op === 'is_not_empty') {
                                finalVal = '';
                            } else if (rawVal.toLowerCase() === 'true') {
                                finalVal = true;
                            } else if (rawVal.toLowerCase() === 'false') {
                                finalVal = false;
                            } else if (/^-?\d+(\.\d+)?$/.test(rawVal) && !/^\d{4}-\d{2}-\d{2}$/.test(rawVal)) {
                                finalVal = rawVal.includes('.') ? parseFloat(rawVal) : parseInt(rawVal, 10);
                            }

                            rules.push({
                                field: field,
                                operator: op,
                                value: finalVal
                            });
                        } else if (child.classList.contains('auto-group-block')) {
                            const subGroupData = serializeGroupElement(child);
                            if (subGroupData.rules.length > 0) {
                                rules.push(subGroupData);
                            }
                        }
                    });
                }

                return {
                    combinator: combinator,
                    rules: rules
                };
            }

            function serializeTreeToJSON() {
                const rootGroup = rootContainer.querySelector('.auto-group-block.is-root');
                if (!rootGroup) return;

                const treeData = serializeGroupElement(rootGroup);
                const jsonStr = JSON.stringify(treeData, null, 2);

                if (filterConditionsArea) filterConditionsArea.value = jsonStr;
                if (conditionRulesArea) conditionRulesArea.value = jsonStr;
            }

            // Deserializes Boolean JSON into DOM Group Tree
            function buildGroupDOMFromData(data, isNested = false) {
                let combinator = 'AND';
                let rulesList = [];

                if (data && typeof data === 'object') {
                    if (Array.isArray(data)) {
                        rulesList = data;
                    } else if (data.combinator && Array.isArray(data.rules)) {
                        combinator = data.combinator;
                        rulesList = data.rules;
                    } else if ('field' in data && 'operator' in data) {
                        rulesList = [data];
                    } else {
                        // Legacy flat dict {"is_agent": true}
                        rulesList = Object.entries(data).map(([k, v]) => ({
                            field: k,
                            operator: '==',
                            value: v
                        }));
                    }
                }

                const groupEl = createGroupBlock(isNested, combinator);
                const container = groupEl.querySelector('.auto-group-rules-container');

                rulesList.forEach(item => {
                    if (item && typeof item === 'object') {
                        if (item.combinator && Array.isArray(item.rules)) {
                            // Sub-group (Parentheses)
                            const subEl = buildGroupDOMFromData(item, true);
                            container.appendChild(subEl);
                        } else if (item.field) {
                            // Single Rule Row
                            const rowEl = createRuleRow(item.field, item.operator || '==', item.value);
                            container.appendChild(rowEl);
                        }
                    }
                });

                checkEmptyContainer(container);
                return groupEl;
            }

            function deserializeJSONToTree() {
                rootContainer.innerHTML = '';
                let rawData = null;

                const rawStr = (filterConditionsArea && filterConditionsArea.value.trim()) ||
                               (conditionRulesArea && conditionRulesArea.value.trim()) || '';

                if (rawStr) {
                    try {
                        rawData = JSON.parse(rawStr);
                    } catch (e) {
                        rawData = null;
                    }
                }

                if (!rawData || (Array.isArray(rawData) && rawData.length === 0)) {
                    const defaultRoot = createGroupBlock(false, 'AND');
                    const defaultField = currentTriggerFields.length > 0 ? currentTriggerFields[0].name : '';
                    defaultRoot.querySelector('.auto-group-rules-container').appendChild(createRuleRow(defaultField, '==', ''));
                    rootContainer.appendChild(defaultRoot);
                } else {
                    const rootGroup = buildGroupDOMFromData(rawData, false);
                    rootContainer.appendChild(rootGroup);
                }
            }

            function updateAllFieldDropdowns() {
                const rows = rootContainer.querySelectorAll('.auto-rule-row');
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

            resetBtn.addEventListener('click', () => {
                rootContainer.innerHTML = '';
                const defaultRoot = createGroupBlock(false, 'AND');
                const defaultField = currentTriggerFields.length > 0 ? currentTriggerFields[0].name : '';
                defaultRoot.querySelector('.auto-group-rules-container').appendChild(createRuleRow(defaultField, '==', ''));
                rootContainer.appendChild(defaultRoot);
                serializeTreeToJSON();
            });

            // Initialize tree from existing JSON
            deserializeJSONToTree();
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

    // 5. ACTION PARAMS ASSISTANT WITH PROMPT PRESETS & CONTEXT INSERTION
    let cachedServices = null;
    const activeParamsAssistants = [];

    async function getRegisteredServices() {
        if (cachedServices) return cachedServices;
        try {
            const resp = await fetch('/api/automation/services/', {
                headers: { 'Accept': 'application/json' }
            });
            if (resp.ok) {
                const data = await resp.json();
                cachedServices = data.services || [];
                return cachedServices;
            }
        } catch (e) {
            console.warn('Failed to fetch automation services:', e);
        }
        return [];
    }

    function setupActionParamsAssistant(container) {
        const actionTypeSelects = container.querySelectorAll('select[name$="action_type"]');

        actionTypeSelects.forEach(select => {
            if (select.dataset.autoParamsAssistantBound) return;
            select.dataset.autoParamsAssistantBound = "true";

            const parentRow = select.closest('.inline-related') || select.closest('fieldset') || select.closest('form');
            if (!parentRow) return;

            const actionParamsArea = parentRow.querySelector('textarea[name$="action_params"]');
            if (!actionParamsArea) return;

            let assistantPanel = null;

            async function updateParamsAssistant() {
                const actionType = select.value;
                if (!assistantPanel) {
                    assistantPanel = document.createElement('div');
                    assistantPanel.className = 'auto-schema-panel';
                    actionParamsArea.parentNode.insertBefore(assistantPanel, actionParamsArea);
                    activeParamsAssistants.push(updateParamsAssistant);
                }

                if (!actionType || actionType === 'none') {
                    assistantPanel.style.display = 'none';
                    return;
                }

                const services = await getRegisteredServices();
                const actionDef = services.find(s => s.name === actionType);

                if (!actionDef) {
                    assistantPanel.style.display = 'none';
                    return;
                }

                assistantPanel.style.display = 'block';

                const presets = actionDef.presets || [];
                const schemaKeys = Object.keys(actionDef.schema || {});

                let presetsHtml = '';
                if (presets.length > 0) {
                    presetsHtml = `
                        <div style="margin-top: 8px;">
                            <span style="font-size: 11px; font-weight: 700; color: #1e293b;">💡 Quick Action Presets (Click to Load):</span>
                            <div class="auto-preset-list">
                                ${presets.map((p, idx) => `
                                    <button type="button" class="auto-preset-btn" data-preset-idx="${idx}" title="${p.description || ''}">
                                        ${p.name}
                                    </button>
                                `).join('')}
                            </div>
                        </div>
                    `;
                }

                // Context pills
                let contextTags = ['{{pk}}', '{{username}}', '{{model}}', '{{now}}'];
                if (currentTriggerFields && currentTriggerFields.length > 0) {
                    currentTriggerFields.forEach(f => {
                        const tag = `{{${f.name}}}`;
                        if (!contextTags.includes(tag) && f.name !== 'id') {
                            contextTags.push(tag);
                        }
                    });
                }

                let schemaHtml = '';
                if (schemaKeys.length > 0) {
                    schemaHtml = `
                        <div class="auto-schema-hint">
                            <strong>📋 Expected Parameters:</strong>
                            ${schemaKeys.map(k => `<div><code>${k}</code>: <span style="opacity:0.85">${actionDef.schema[k]}</span></div>`).join('')}
                        </div>
                    `;
                }

                assistantPanel.innerHTML = `
                    <div class="auto-panel-header">
                        <span>🤖 Action Assistant: <strong>${actionDef.name}</strong></span>
                        <span style="font-size: 11px; font-weight: normal; color: #64748b;">${actionDef.category}</span>
                    </div>
                    <div style="font-size: 11.5px; color: #475569; margin-bottom: 6px;">
                        ${actionDef.description}
                    </div>
                    ${presetsHtml}
                    <div style="margin-top: 8px; border-top: 1px dashed #cbd5e1; padding-top: 6px;">
                        <span style="font-size: 11px; font-weight: 600; color: #334155; margin-right: 6px;">⚡ Insert Context Variables:</span>
                        ${contextTags.map(tag => `<span class="auto-tag-context" data-val="${tag}">${tag}</span>`).join('')}
                    </div>
                    ${schemaHtml}
                `;

                // Bind preset clicks
                assistantPanel.querySelectorAll('.auto-preset-btn').forEach(btn => {
                    btn.addEventListener('click', () => {
                        const idx = parseInt(btn.getAttribute('data-preset-idx'), 10);
                        const chosenPreset = presets[idx];
                        if (chosenPreset && chosenPreset.params) {
                            actionParamsArea.value = JSON.stringify(chosenPreset.params, null, 2);
                            actionParamsArea.focus();
                        }
                    });
                });

                // Bind context tag clicks
                assistantPanel.querySelectorAll('.auto-tag-context').forEach(tag => {
                    tag.addEventListener('click', () => {
                        const text = tag.getAttribute('data-val');
                        const start = actionParamsArea.selectionStart;
                        const end = actionParamsArea.selectionEnd;
                        const val = actionParamsArea.value;
                        actionParamsArea.value = val.substring(0, start) + text + val.substring(end);
                        actionParamsArea.focus();
                        actionParamsArea.selectionStart = actionParamsArea.selectionEnd = start + text.length;
                    });
                });
            }

            select.addEventListener('change', updateParamsAssistant);
            if (select.value) {
                updateParamsAssistant();
            }
        });
    }

    setupActionMappingAssistant(document);
    setupActionParamsAssistant(document);

    const observer = new MutationObserver((mutations) => {
        mutations.forEach(mutation => {
            if (mutation.addedNodes.length > 0) {
                setupActionMappingAssistant(document);
                setupActionParamsAssistant(document);
            }
        });
    });
    observer.observe(document.body, { childList: true, subtree: true });
});
