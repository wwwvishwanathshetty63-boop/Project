// Highlight the active menu item based on current URL
document.addEventListener('DOMContentLoaded', () => {
    // Set active nav item
    const currentPath = window.location.pathname;
    const navItems = document.querySelectorAll('.menu-item');

    // Default to index if at root
    const pageName = currentPath.split('/').pop() || 'index.html';

    navItems.forEach(item => {
        const itemPage = item.getAttribute('href');
        if (itemPage === pageName) {
            item.classList.add('active');
        } else {
            item.classList.remove('active');
        }
    });

    // ── Populate sidebar with real logged-in user ──────────────
    const user = (typeof getUser === 'function') ? getUser() : (JSON.parse(localStorage.getItem('auth_user') || 'null'));
    if (user) {
        const initials = (user.name || user.email || 'U').split(' ').map(w => w[0]).join('').slice(0,2).toUpperCase();
        const displayName = user.name || user.email || 'User';
        const role = user.role || 'Admin';

        // Sidebar footer
        document.querySelectorAll('.sidebar-footer .user-avatar-small').forEach(el => el.textContent = initials);
        document.querySelectorAll('.sidebar-footer .user-name').forEach(el => el.textContent = displayName);
        document.querySelectorAll('.sidebar-footer .user-role').forEach(el => el.textContent = role);

        // Topbar avatar(s)
        document.querySelectorAll('.topbar-right .user-avatar-small').forEach(el => el.textContent = initials);
    }

    // Handle Mobile Menu
    const mobileMenuBtn = document.querySelector('.mobile-menu-btn');
    const sidebar = document.querySelector('.sidebar');

    if (mobileMenuBtn && sidebar) {
        mobileMenuBtn.addEventListener('click', () => {
            sidebar.classList.toggle('show');
        });

        // Close sidebar on click outside on mobile
        document.addEventListener('click', (e) => {
            if (window.innerWidth <= 768 &&
                !sidebar.contains(e.target) &&
                !mobileMenuBtn.contains(e.target) &&
                sidebar.classList.contains('show')) {
                sidebar.classList.remove('show');
            }
        });
    }

    // Handle user action buttons (mock functionality)
    const refreshBtn = document.getElementById('btn-refresh');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', (e) => {
            e.preventDefault();
            const icon = refreshBtn.querySelector('i');
            icon.classList.add('fa-spin');

            setTimeout(() => {
                icon.classList.remove('fa-spin');

                // Fetch fresh data if the functions exist on the current page
                if (typeof loadDashboardData === 'function') loadDashboardData();
                const endpointsTbody = document.querySelector('#all-endpoints-table tbody');
                if (endpointsTbody && typeof loadEndpointsTable === 'function') loadEndpointsTable(endpointsTbody);
                const usersTbody = document.querySelector('#users-table tbody');
                if (usersTbody && typeof loadAdminUsersTable === 'function') loadAdminUsersTable(usersTbody);

                window.showNotification('Data refreshed successfully');
            }, 1000);
        });
    }

    // Mock notification function
    window.showNotification = function (message) {
        if (typeof showToast === 'function') {
            showToast(message, 'success');
        } else {
            console.log("Notification:", message);
        }
    };

    // Global Topbar Actions
    const notificationBtn = document.querySelector('.topbar-action[title="Notifications"]');
    if (notificationBtn) {
        notificationBtn.addEventListener('click', () => {
            window.showNotification('You have 0 new notifications.');
        });
    }

    const logoutBtn = document.getElementById('logout-btn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', () => {
            if (typeof logout === 'function') logout();
        });
    }

    // Add / Edit Endpoint Modal Logic
    const btnAddEndpoint = document.getElementById('btn-add-endpoint');
    const addEndpointModal = document.getElementById('addEndpointModal');
    const closeEndpointModal = document.getElementById('close-endpoint-modal');
    const cancelEndpointModal = document.getElementById('cancel-endpoint-modal');
    const addEndpointForm = document.getElementById('add-endpoint-form');

    let editEndpointId = null;

    if (addEndpointModal) {
        const openModalForAdd = () => {
            editEndpointId = null;
            addEndpointModal.querySelector('h3').textContent = 'Add New Endpoint';
            addEndpointForm.querySelector('button[type="submit"]').textContent = 'Add Endpoint';
            addEndpointForm.reset();
            const errorEl = document.getElementById('endpoint-error');
            if (errorEl) errorEl.style.display = 'none';
            const monitorTypeRadio = document.querySelector('input[name="monitor_type"][value="url"]');
            if (monitorTypeRadio) monitorTypeRadio.checked = true;
            const apiKeyGroup = document.getElementById('api-key-group');
            if (apiKeyGroup) apiKeyGroup.style.display = 'none';
            const apiKeyInput = document.getElementById('endpoint-api-key');
            if (apiKeyInput) { apiKeyInput.required = false; apiKeyInput.value = ''; }
            const urlWrapper = document.getElementById('url-group-wrapper');
            if (urlWrapper) urlWrapper.style.display = 'block';
            const endpointUrl = document.getElementById('endpoint-url');
            if (endpointUrl) endpointUrl.required = true;
            const aiDetectBadge = document.getElementById('ai-detect-badge');
            if (aiDetectBadge) aiDetectBadge.style.display = 'none';
            addEndpointModal.style.display = 'flex';
        };

        if (btnAddEndpoint) {
            btnAddEndpoint.addEventListener('click', openModalForAdd);
        }

        const closeEndpoint = () => {
            addEndpointModal.style.display = 'none';
            if (addEndpointForm) addEndpointForm.reset();
            editEndpointId = null;
        };

        if (closeEndpointModal) closeEndpointModal.addEventListener('click', closeEndpoint);
        if (cancelEndpointModal) cancelEndpointModal.addEventListener('click', closeEndpoint);

        // Monitor Type Radio Logic
        const monitorRadios = document.querySelectorAll('input[name="monitor_type"]');
        monitorRadios.forEach(radio => {
            radio.addEventListener('change', (e) => {
                const isApiKey = e.target.value === 'api_key';
                const keyGroup = document.getElementById('api-key-group');
                const keyInput = document.getElementById('endpoint-api-key');
                const urlWrapper = document.getElementById('url-group-wrapper');

                if (keyGroup && keyInput && urlWrapper) {
                    keyGroup.style.display = 'block'; // Always visible! (User requested for Custom URL)
                    keyInput.required = isApiKey;
                    
                    // Hide URL field only if "Secured API" auto-detect mode is selected
                    urlWrapper.style.display = isApiKey ? 'none' : 'block';
                    document.getElementById('endpoint-url').required = !isApiKey;
                    
                    if (!isApiKey) {
                        document.getElementById('ai-detect-badge').style.display = 'none';
                    }
                }
            });
        });

        // AI URL Auto-Detection Logic
        const apiKeyInputEl = document.getElementById('endpoint-api-key');
        if (apiKeyInputEl) {
            apiKeyInputEl.addEventListener('blur', async (e) => {
                const val = e.target.value.trim();
                const badge = document.getElementById('ai-detect-badge');
                const urlInput = document.getElementById('endpoint-url');
                
                // Only trigger if in 'api_key' mode and a value exists
                if (!val || document.querySelector('input[name="monitor_type"]:checked').value !== 'api_key') {
                    if (badge) badge.style.display = 'none';
                    return;
                }
                
                if (badge) {
                    badge.style.display = 'flex';
                    badge.style.color = 'var(--text-color)';
                    badge.style.backgroundColor = 'rgba(255,255,255,0.1)';
                    badge.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> AI Detecting...';
                }
                
                try {
                    const res = await fetch('/api/endpoints/detect-url', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'Authorization': `Bearer ${localStorage.getItem('token')}`
                        },
                        body: JSON.stringify({ api_key: val })
                    });
                    
                    const data = await res.json();
                    
                    if (!res.ok) throw new Error(data.error || 'Failed to detect URL');
                    
                    // Success!
                    if (urlInput) urlInput.value = data.base_url;
                    if (badge) {
                        badge.style.color = '#10b981'; // Success Green
                        badge.style.backgroundColor = 'rgba(16, 185, 129, 0.1)';
                        badge.innerHTML = `<i class="fa-solid fa-check-circle"></i> ${data.provider} Detected`;
                    }
                    
                } catch (err) {
                    // Javascript Fallback Detect
                    const jsFallback = (k) => {
                        k = k.trim();
                        if (k.startsWith('sk_live_') || k.startsWith('sk_test_')) return { p: 'Stripe', u: 'https://api.stripe.com/v1/balance' };
                        if (k.startsWith('ghp_')) return { p: 'GitHub', u: 'https://api.github.com/user' };
                        if (k.startsWith('SG.')) return { p: 'SendGrid', u: 'https://api.sendgrid.com/v3/scopes' };
                        if (k.startsWith('xoxb-') || k.startsWith('xoxp-')) return { p: 'Slack', u: 'https://slack.com/api/api.test' };
                        if (k.match(/^sk-[a-zA-Z0-9]{48}$/) || k.startsWith('sk-proj-')) return { p: 'OpenAI', u: 'https://api.openai.com/v1/models' };
                        if (k.length === 64 && /^[0-9a-fA-F]+$/.test(k)) return { p: 'VirusTotal', u: 'https://www.virustotal.com/api/v3/users/__logged_in__' };
                        return null;
                    };
                    
                    const fallback = jsFallback(val);
                    if (fallback) {
                        if (urlInput) urlInput.value = fallback.u;
                        if (badge) {
                            badge.style.color = '#10b981'; // Success Green
                            badge.style.backgroundColor = 'rgba(16, 185, 129, 0.1)';
                            badge.innerHTML = `<i class="fa-solid fa-bolt"></i> ${fallback.p} Detected (Fallback)`;
                        }
                    } else {
                        // Fail gracefully, show the URL field so they can enter manually
                        if (badge) {
                            badge.style.color = '#ef4444'; // Error Red
                            badge.style.backgroundColor = 'rgba(239, 68, 68, 0.1)';
                            badge.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> Auto-detect failed`;
                        }
                        const urlWrapper = document.getElementById('url-group-wrapper');
                        if (urlWrapper) {
                            urlWrapper.style.display = 'block'; // Force show
                            if (urlInput) urlInput.required = true;
                        }
                    }
                }
            });
        }

        // Global functions for table row actions
        window.openEditModal = async function (id) {
            try {
                const data = await apiRequest(`/api/endpoints/${id}`);
                const ep = data.endpoint;

                document.getElementById('endpoint-name').value = ep.name;
                document.getElementById('endpoint-url').value = ep.url;
                document.getElementById('endpoint-method').value = ep.method;
                document.getElementById('endpoint-interval').value = ep.interval || 60;
                
                // If endpoint has an API key masked value, assume it's secured
                const hasApiKey = ep.api_key_masked ? true : false;
                const radio = document.querySelector(`input[name="monitor_type"][value="${hasApiKey ? 'api_key' : 'url'}"]`);
                if (radio) {
                    radio.checked = true;
                    radio.dispatchEvent(new Event('change'));
                }

                // API key is never sent back from server (masked), so clear the field
                const editKeyInput = document.getElementById('endpoint-api-key');
                if (editKeyInput) editKeyInput.value = '';

                editEndpointId = id;
                addEndpointModal.querySelector('h3').textContent = 'Edit Endpoint';
                addEndpointForm.querySelector('button[type="submit"]').textContent = 'Save Changes';
                addEndpointModal.style.display = 'flex';
            } catch (err) {
                if (typeof showToast === 'function') showToast('Failed to load details', 'error');
                else alert('Failed to load details');
            }
        };

        window.deleteEndpoint = async function (id, name) {
            if (!confirm(`Are you sure you want to delete "${name}"? This cannot be undone.`)) return;
            try {
                await apiRequest(`/api/endpoints/${id}`, { method: 'DELETE' });
                if (typeof showToast === 'function') showToast(`"${name}" deleted`, 'success');
                else window.showNotification(`Endpoint "${name}" deleted.`);
                // Reload dashboard data — fires endpointsReady which re-renders cards
                if (typeof loadDashboardData === 'function') loadDashboardData();
            } catch (err) {
                if (typeof showToast === 'function') showToast(err.message || 'Delete failed', 'error');
                else alert(err.message);
            }
        };

        if (addEndpointForm) {
            addEndpointForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                const submitBtn = addEndpointForm.querySelector('button[type="submit"]');
                const originalText = submitBtn.textContent;

                try {
                    submitBtn.disabled = true;
                    submitBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> ${editEndpointId ? 'Saving...' : 'Adding...'}`;

                    const name = document.getElementById('endpoint-name').value;
                    const url = document.getElementById('endpoint-url').value;
                    const method = document.getElementById('endpoint-method').value;
                    const interval = document.getElementById('endpoint-interval').value;
                    const monitorType = document.querySelector('input[name="monitor_type"]:checked').value;
                    const api_key = document.getElementById('endpoint-api-key')?.value;

                    const body = { name, url, method, interval };
                    if (api_key && api_key.trim()) body.api_key = api_key.trim();

                    if (editEndpointId) {
                        await apiRequest(`/api/endpoints/${editEndpointId}`, {
                            method: 'PUT',
                            body
                        });
                        window.showNotification('Endpoint updated successfully!');
                    } else {
                        await apiRequest('/api/endpoints', {
                            method: 'POST',
                            body
                        });
                        window.showNotification('Endpoint added successfully!');
                    }

                    closeEndpoint();

                    // Reload dashboard which fires endpointsReady → re-renders cards
                    if (typeof loadDashboardData === 'function') loadDashboardData();

                } catch (error) {
                    const errorEl = document.getElementById('endpoint-error');
                    if (errorEl) {
                        let msg = error.message || 'Failed to save endpoint';
                        if (error.detail) msg += `: ${error.detail}`;
                        const msgSpan = errorEl.querySelector('.error-message');
                        if (msgSpan) msgSpan.textContent = msg;
                        errorEl.style.display = 'flex';
                        errorEl.style.animation = 'none';
                        errorEl.offsetHeight;
                        errorEl.style.animation = null;
                    } else {
                        if (typeof showToast === 'function') {
                            showToast(error.message || 'Failed to save endpoint', 'error');
                        } else {
                            alert(error.message || 'Failed to save endpoint');
                        }
                    }
                } finally {
                    submitBtn.disabled = false;
                    submitBtn.textContent = originalText;
                }
            });
        }
    }

    // Handle dummy buttons on Logs and Alerts pages
    document.querySelectorAll('.btn').forEach(btn => {
        if (btn.textContent.includes('Export Logs')) {
            btn.addEventListener('click', () => {
                window.showNotification('Logs exported successfully to CSV.');
            });
        } else if (btn.textContent.includes('New Alert Rule')) {
            btn.addEventListener('click', () => {
                window.showNotification('Alert rule component loading...');
                // Dummy delay modal opening
            });
        }
    });
});
