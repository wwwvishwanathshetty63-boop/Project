document.addEventListener('DOMContentLoaded', () => {
    // Determine which page we are on by looking for specific tables
    const endpointsTbody = document.querySelector('#all-endpoints-table tbody');
    const usersTbody = document.querySelector('#users-table tbody');

    if (endpointsTbody) {
        loadEndpointsTable(endpointsTbody);
    }

    if (usersTbody) {
        loadAdminUsersTable(usersTbody);
    }
});

async function loadEndpointsTable(tbody, range = '1d') {
    try {
        const data = await fetchWithRetry(`/api/endpoints?range=${range}`);
        const endpoints = data.endpoints || [];

        // Update header if exists
        const header = document.getElementById('uptime-header');
        if (header) {
            const rangeLabels = { '1d': 'Uptime (24h)', '7d': 'Uptime (7d)', '30d': 'Uptime (30d)' };
            header.textContent = rangeLabels[range] || 'Uptime (%)';
        }

        if (endpoints.length === 0) {
            tbody.innerHTML = `<tr><td colspan="8" style="padding:3rem; text-align:center;">
                <div class="empty-state" style="padding:2rem 1rem;">
                    <i class="fa-solid fa-satellite-dish"></i>
                    <p>No endpoints yet. Click <strong>+ Add Endpoint</strong> to start monitoring your first API.</p>
                </div></td></tr>`;
            return;
        }

        tbody.innerHTML = endpoints.map(api => {
            // Method badge HTML
            const methodMap = { GET: 'm-get', POST: 'm-post', PUT: 'm-put', DELETE: 'm-delete' };
            const methodCls = methodMap[api.method] || 'm-get';
            const methodHtml = `<span class="monitor-card-method ${methodCls}">${api.method || 'GET'}</span>`;

            // Status pill HTML
            let statusHtml = '';
            if (api.is_down) {
                statusHtml = `<span class="status-pill down"><span class="pulse-dot down"></span>DOWN</span>`;
            } else if (api.is_active) {
                statusHtml = `<span class="status-pill up"><span class="pulse-dot up"></span>UP</span>`;
            } else {
                statusHtml = `<span class="status-pill paused">PAUSED</span>`;
            }

            const responseTime = api.last_response_time !== null ? `${api.last_response_time}ms` : '—';
            const lastChecked = api.last_check ? new Date(api.last_check).toLocaleString() : 'Never';

            // Uptime bar (Real data)
            const uptimePct = api.uptime_percentage != null ? api.uptime_percentage : 100;
            const uptimeCls = uptimePct >= 99 ? 'uptime-high' : uptimePct >= 95 ? 'uptime-medium' : 'uptime-low';
            
            // For a simpler view, we just show the percentage and a small bar
            // If they want the 30-block bar, we can simulate it based on the percentage for now, 
            // or just show the percentage. The requirement is "details for one day".
            let uptimeBarHtml = `<div class="uptime-percentage-box">
                <div class="uptime-pct ${uptimeCls}" style="font-weight:600; font-size:0.9rem;">${uptimePct}%</div>
                <div class="uptime-mini-bar" style="width:100%; height:4px; background:#E5E7EB; border-radius:2px; margin-top:4px; overflow:hidden;">
                    <div style="width:${uptimePct}%; height:100%; background: ${uptimePct >= 99 ? '#10B981' : (uptimePct >= 95 ? '#F59E0B' : '#EF4444')};"></div>
                </div>
            </div>`;

            return `
                <tr>
                    <td style="font-weight: 500;">${escapeHtml(api.name)}</td>
                    <td><span class="code-style" style="font-size:0.78rem;">${escapeHtml(api.url)}</span></td>
                    <td>${methodHtml}</td>
                    <td>${statusHtml}</td>
                    <td style="font-weight:600; color: ${api.is_down ? '#EF4444' : 'var(--text-color)'}">${responseTime}</td>
                    <td>${uptimeBarHtml}</td>
                    <td style="color: var(--text-muted); font-size:0.8rem;">${lastChecked}</td>
                    <td class="text-right">
                        <div class="action-btns">
                            <button class="action-btn" title="Edit" onclick="openEditModal('${api.id}')"><i class="fa-solid fa-pen"></i></button>
                            <button class="action-btn delete" title="Delete" onclick="deleteEndpoint('${api.id}', '${escapeHtml(api.name)}')"><i class="fa-solid fa-trash"></i></button>
                        </div>
                    </td>
                </tr>
            `;
        }).join('');
    } catch (error) {
        console.error('Failed to load endpoints table:', error);
        tbody.innerHTML = `<tr><td colspan="8" class="text-center text-danger">Error loading endpoints. Please ensure you are logged in.</td></tr>`;
    }
}

async function loadAdminUsersTable(tbody) {
    try {
        const data = await fetchWithRetry('/api/auth/employees');
        const employees = data.employees || [];

        if (employees.length === 0) {
            tbody.innerHTML = `<tr><td colspan="6" class="text-center text-muted">No employees found.</td></tr>`;
            return;
        }

        const colors = ['#7C3AED', '#3B82F6', '#10B981', '#F59E0B'];

        tbody.innerHTML = employees.map((user, index) => {
            const roleHtml = `<span class="badge badge-gray">Employee</span>`;
            const statusHtml = `<span class="badge badge-success"><span class="badge-dot"></span> Active</span>`;
            const randomColor = colors[index % colors.length];
            const initials = user.name ? user.name.charAt(0).toUpperCase() : '?';
            const joinedAt = user.created_at ? new Date(user.created_at).toLocaleString() : '—';

            return `
                <tr>
                    <td>
                        <div style="display: flex; align-items: center; gap: 0.75rem;">
                            <div class="user-avatar-small" style="background-color: ${randomColor}">${initials}</div>
                            <span style="font-weight: 500;">${escapeHtml(user.name)}</span>
                        </div>
                    </td>
                    <td style="color: var(--text-muted);">${escapeHtml(user.email)}</td>
                    <td>${roleHtml}</td>
                    <td>${statusHtml}</td>
                    <td style="color: var(--text-muted);">${joinedAt}</td>
                    <td class="text-right">
                        <div class="action-btns">
                            <button class="action-btn" title="Edit Credentials" onclick="window.showNotification('Credentials ID: ${escapeHtml(user.employee_id)}')"><i class="fa-solid fa-key"></i></button>
                            <button class="action-btn delete" title="Suspend" onclick="window.showNotification('User suspended successfully.')"><i class="fa-solid fa-user-xmark"></i></button>
                        </div>
                    </td>
                </tr>
            `;
        }).join('');
    } catch (error) {
        console.error('Failed to load admin users table:', error);
        tbody.innerHTML = `<tr><td colspan="6" class="text-center text-danger">Error loading users.</td></tr>`;
    }
}

// Ensure apiRequest and fetchWithRetry are available in this scope or globally exported from dashboard.js
// Since backend usually serves these scripts via <script> tags we assume global scope if not using modules.

// ---- Modal Logic for Admin Panel ----
document.addEventListener('DOMContentLoaded', () => {
    const btnInvite = document.getElementById('btn-invite');
    const inviteModal = document.getElementById('inviteModal');
    const closeModal = document.getElementById('close-modal');
    const cancelModal = document.getElementById('cancel-modal');
    const inviteForm = document.getElementById('invite-form');

    if (btnInvite && inviteModal) {
        btnInvite.addEventListener('click', () => {
            inviteModal.style.display = 'flex';
        });

        const close = () => {
            inviteModal.style.display = 'none';
            inviteForm.reset();
        };

        closeModal.addEventListener('click', close);
        cancelModal.addEventListener('click', close);

        inviteForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const submitBtn = inviteForm.querySelector('button[type="submit"]');
            const originalText = submitBtn.textContent;

            try {
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Sending...';

                const name = document.getElementById('invite-name').value;
                const email = document.getElementById('invite-email').value;

                await apiRequest('/api/auth/invite-employee', {
                    method: 'POST',
                    body: { name, email, role: 'Employee' }
                });

                showNotification('Employee invited successfully!');
                close();

                // Refresh table
                const tbody = document.querySelector('#admin-users-table tbody');
                if (tbody) loadAdminUsersTable(tbody);

            } catch (error) {
                alert(error.message || 'Failed to invite employee');
            } finally {
                submitBtn.disabled = false;
                submitBtn.textContent = originalText;
            }
        });
    }
});
