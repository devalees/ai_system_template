/**
 * Hermes Profile Live Selector & Real-Time Reload Widget.
 *
 * Enhances Django Admin with an interactive dropdown of Hermes profiles,
 * an AJAX reload button (🔄) querying /api/hermes/profiles/, and auto-fill
 * of profile metadata (role, display name, description).
 */

document.addEventListener('DOMContentLoaded', function () {
    // Style definition for animations and buttons
    const style = document.createElement('style');
    style.textContent = `
        .hermes-profile-container {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            flex-wrap: wrap;
        }
        .hermes-reload-btn {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 5px 12px;
            background: #0284c7;
            color: #ffffff !important;
            border: 1px solid #0369a1;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
            text-decoration: none;
            line-height: 1.4;
        }
        .hermes-reload-btn:hover {
            background: #0369a1;
            box-shadow: 0 2px 4px rgba(0,0,0,0.15);
        }
        .hermes-reload-btn:active {
            transform: scale(0.97);
        }
        .hermes-spin-active {
            animation: hermes-spin 0.8s linear infinite;
            display: inline-block;
        }
        @keyframes hermes-spin {
            100% { transform: rotate(360deg); }
        }
        .hermes-status-badge {
            font-size: 11px;
            font-weight: 600;
            padding: 3px 8px;
            border-radius: 4px;
            transition: all 0.3s ease;
        }
        .hermes-status-success {
            background: #dcfce7;
            color: #15803d;
            border: 1px solid #bbf7d0;
        }
        .hermes-status-error {
            background: #fee2e2;
            color: #b91c1c;
            border: 1px solid #fecaca;
        }
        .agent-fields-highlight {
            border-left: 3px solid #0284c7 !important;
            padding-left: 10px;
            transition: all 0.3s ease;
        }
    `;
    document.head.appendChild(style);

    function initHermesProfileWidget(selectEl) {
        if (!selectEl || selectEl.dataset.hermesInitialized) return;
        selectEl.dataset.hermesInitialized = "true";

        // Wrap select in container
        const container = document.createElement('div');
        container.className = 'hermes-profile-container';
        selectEl.parentNode.insertBefore(container, selectEl);
        container.appendChild(selectEl);

        // Create Reload Button
        const reloadBtn = document.createElement('button');
        reloadBtn.type = 'button';
        reloadBtn.className = 'hermes-reload-btn';
        reloadBtn.innerHTML = '<span class="hermes-spin-icon">🔄</span> Reload Profiles';

        // Create Status Badge
        const statusBadge = document.createElement('span');
        statusBadge.className = 'hermes-status-badge';
        statusBadge.style.display = 'none';

        container.appendChild(reloadBtn);
        container.appendChild(statusBadge);

        // Store profiles cache for auto-fill
        let cachedProfiles = [];

        async function fetchProfiles(animate = true) {
            const icon = reloadBtn.querySelector('.hermes-spin-icon');
            if (animate && icon) icon.classList.add('hermes-spin-active');
            reloadBtn.disabled = true;

            try {
                const res = await fetch('/api/hermes/profiles/');
                if (!res.ok) throw new Error(`HTTP ${res.status}`);
                const data = await res.json();
                cachedProfiles = data.profiles || [];

                const currentVal = selectEl.value;
                selectEl.innerHTML = '';

                // Default empty option
                const defaultOpt = document.createElement('option');
                defaultOpt.value = '';
                defaultOpt.textContent = '-- Select Hermes Profile --';
                selectEl.appendChild(defaultOpt);

                let matched = false;
                cachedProfiles.forEach(p => {
                    const opt = document.createElement('option');
                    opt.value = p.name;
                    opt.textContent = `${p.display_name} (${p.name})`;
                    if (p.name === currentVal) {
                        opt.selected = true;
                        matched = true;
                    }
                    selectEl.appendChild(opt);
                });

                if (currentVal && !matched) {
                    const customOpt = document.createElement('option');
                    customOpt.value = currentVal;
                    customOpt.textContent = `${currentVal} (Custom / Unlisted)`;
                    customOpt.selected = true;
                    selectEl.appendChild(customOpt);
                }

                statusBadge.textContent = `✓ ${cachedProfiles.length} Profiles loaded`;
                statusBadge.className = 'hermes-status-badge hermes-status-success';
                statusBadge.style.display = 'inline-block';
                setTimeout(() => { statusBadge.style.display = 'none'; }, 3500);

            } catch (err) {
                console.error('Failed to reload Hermes profiles:', err);
                statusBadge.textContent = '✕ Error loading profiles';
                statusBadge.className = 'hermes-status-badge hermes-status-error';
                statusBadge.style.display = 'inline-block';
                setTimeout(() => { statusBadge.style.display = 'none'; }, 4000);
            } finally {
                if (icon) icon.classList.remove('hermes-spin-active');
                reloadBtn.disabled = false;
            }
        }

        reloadBtn.addEventListener('click', function (e) {
            e.preventDefault();
            fetchProfiles(true);
        });

        // Auto-fill related fields when a profile is selected
        selectEl.addEventListener('change', function () {
            const selectedName = this.value;
            if (!selectedName) return;

            const profile = cachedProfiles.find(p => p.name === selectedName);
            const prefix = selectEl.name.replace('hermes_profile_name', '');

            // Scope query selectors to the current form/inline row
            const formContainer = selectEl.closest('.form-row, .inline-related, fieldset, form') || document;

            // Find companion fields
            const displayNameInput = formContainer.querySelector(`input[name="${prefix}display_name"]`) || document.getElementById('id_display_name');
            const roleSelect = formContainer.querySelector(`select[name="${prefix}role"]`) || document.getElementById('id_role');
            const descInput = formContainer.querySelector(`textarea[name="${prefix}description"]`) || document.getElementById('id_description');
            const isAgentCheckbox = formContainer.querySelector(`input[name="${prefix}is_agent"]`) || document.getElementById('id_is_agent');
            const userTypeSelect = formContainer.querySelector(`select[name="${prefix}user_type"]`) || document.getElementById('id_user_type');

            if (isAgentCheckbox && !isAgentCheckbox.checked) {
                isAgentCheckbox.checked = true;
                isAgentCheckbox.dispatchEvent(new Event('change'));
            }
            if (userTypeSelect && userTypeSelect.value !== 'agent') {
                userTypeSelect.value = 'agent';
                userTypeSelect.dispatchEvent(new Event('change'));
            }

            if (profile) {
                if (displayNameInput && (!displayNameInput.value || displayNameInput.value === displayNameInput.defaultValue)) {
                    displayNameInput.value = profile.display_name;
                }
                if (roleSelect && profile.role) {
                    for (let i = 0; i < roleSelect.options.length; i++) {
                        if (roleSelect.options[i].value === profile.role) {
                            roleSelect.selectedIndex = i;
                            break;
                        }
                    }
                }
                if (descInput && (!descInput.value || descInput.value.trim() === '')) {
                    descInput.value = profile.description || '';
                }
            }
        });

        // If options are empty, load initially
        if (selectEl.options.length <= 1) {
            fetchProfiles(false);
        }
    }

    // Initialize all matching select elements (standalone Profile form and User ProfileInline)
    document.querySelectorAll('select[name$="hermes_profile_name"], select#id_hermes_profile_name').forEach(initHermesProfileWidget);
});
