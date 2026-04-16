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

        // Global functions for table row actions
        window.openEditModal = async function (id) {
            try {
                const data = await apiRequest(`/api/endpoints/${id}`);
                const ep = data.endpoint;

                document.getElementById('endpoint-name').value = ep.name;
                document.getElementById('endpoint-url').value = ep.url;
                document.getElementById('endpoint-method').value = ep.method;
                document.getElementById('endpoint-interval').value = ep.interval || 60;

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
            if (!confirm(`Are you sure you want to delete the endpoint "${name}"?`)) return;
            try {
                // Assuming backend supports DELETE /api/endpoints/{id}
                await apiRequest(`/api/endpoints/${id}`, { method: 'DELETE' });
                window.showNotification(`Endpoint "${name}" deleted.`);

                const tbody = document.querySelector('#all-endpoints-table tbody');
                if (tbody && typeof loadEndpointsTable === 'function') loadEndpointsTable(tbody);
                if (typeof loadDashboardData === 'function') loadDashboardData();
            } catch (err) {
                if (typeof showToast === 'function') showToast(err.message, 'error');
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

                    if (editEndpointId) {
                        await apiRequest(`/api/endpoints/${editEndpointId}`, {
                            method: 'PUT',
                            body: { name, url, method, interval }
                        });
                        window.showNotification('Endpoint updated successfully!');
                    } else {
                        await apiRequest('/api/endpoints', {
                            method: 'POST',
                            body: { name, url, method, interval }
                        });
                        window.showNotification('Endpoint added successfully!');
                    }

                    closeEndpoint();

                    // Refresh tables
                    const tbody = document.querySelector('#all-endpoints-table tbody');
                    if (tbody && typeof loadEndpointsTable === 'function') loadEndpointsTable(tbody);
                    if (typeof loadDashboardData === 'function') loadDashboardData();

                } catch (error) {
                    if (typeof showToast === 'function') {
                        showToast(error.message || 'Failed to save endpoint', 'error');
                    } else {
                        alert(error.message || 'Failed to save endpoint');
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
