/**
 * API Monitor SaaS — Dashboard Module
 * Stats display, endpoint management, Chart.js graphs, auto-refresh.
 * Employee management (company role only).
 */

let responseChart = null;
let refreshInterval = null;
let chartRefreshInterval = null;

// ---- Init Dashboard ----
function initDashboard() {
    if (!isAuthenticated()) {
        window.location.href = 'index.html';
        return;
    }

    setupNavbar();
    setupRoleBasedUI();
    loadDashboardData();

    // Auto-refresh stats & endpoints every 30 seconds
    refreshInterval = setInterval(loadDashboardData, 30000);

    // Real-time chart refresh every 10 seconds
    chartRefreshInterval = setInterval(refreshChartOnly, 10000);

    // Add endpoint modal
    const addEndpointBtn = document.getElementById('add-endpoint-btn');
    if (addEndpointBtn) {
        addEndpointBtn.addEventListener('click', openAddModal);
    }
    document.getElementById('modal-close-btn').addEventListener('click', closeModal);
    document.getElementById('modal-cancel-btn').addEventListener('click', closeModal);
    document.getElementById('endpoint-form').addEventListener('submit', handleEndpointSubmit);
    document.getElementById('edit-modal-close-btn').addEventListener('click', closeEditModal);
    document.getElementById('edit-modal-cancel-btn').addEventListener('click', closeEditModal);
    document.getElementById('edit-endpoint-form').addEventListener('submit', handleEditSubmit);

    // Close modal on overlay click
    document.getElementById('add-modal').addEventListener('click', (e) => {
        if (e.target === e.currentTarget) closeModal();
    });
    document.getElementById('edit-modal').addEventListener('click', (e) => {
        if (e.target === e.currentTarget) closeEditModal();
    });

    // Invite employee form (company only)
    const inviteForm = document.getElementById('invite-employee-form');
    if (inviteForm) {
        inviteForm.addEventListener('submit', handleInviteEmployee);
    }
}

function setupNavbar() {
    const user = getUser();
    if (!user) return;

    const userNameEl = document.getElementById('user-name');
    const avatarEl = document.getElementById('user-avatar');
    const logoutBtn = document.getElementById('logout-btn');

    if (userNameEl) userNameEl.textContent = user.name;
    if (avatarEl) avatarEl.textContent = user.name.charAt(0).toUpperCase();
    if (logoutBtn) logoutBtn.addEventListener('click', logout);
}

function setupRoleBasedUI() {
    const user = getUser();
    if (!user) return;

    const isCompany = user.role === 'company';

    // Show/hide "Add Endpoint" button for employees
    const addEndpointBtn = document.getElementById('add-endpoint-btn');
    if (addEndpointBtn && !isCompany) {
        addEndpointBtn.style.display = 'none';
    }

    // Show employee management section for company accounts
    const empSection = document.getElementById('employee-management-section');
    if (empSection && isCompany) {
        empSection.style.display = 'block';
        loadEmployees();
    }
}

// ---- Retry helper with exponential backoff ----
async function fetchWithRetry(endpoint, maxRetries = 3) {
    for (let attempt = 1; attempt <= maxRetries; attempt++) {
        try {
            return await apiRequest(endpoint);
        } catch (error) {
            // Don't retry auth errors (user is being redirected to login)
            if (error.message.includes('Session expired')) throw error;

            // On last attempt, throw the error
            if (attempt === maxRetries) throw error;

            // Only retry on network errors or 5xx server errors
            if (error.isNetworkError || error.message.includes('Server error') || error.message.includes('500')) {
                const delay = Math.min(1000 * Math.pow(2, attempt - 1), 5000);
                await new Promise(resolve => setTimeout(resolve, delay));
                continue;
            }

            // Non-retryable errors — throw immediately
            throw error;
        }
    }
}

// ---- Load All Dashboard Data ----
async function loadDashboardData() {
    let statsOk = false;
    let chartOk = false;

    // Load stats and chart independently — one failure doesn't block the other
    try {
        const statsData = await fetchWithRetry('/api/dashboard/stats');
        renderStats(statsData.stats);
        renderEndpoints(statsData.endpoints);
        statsOk = true;
    } catch (error) {
        console.error('Failed to load stats:', error);
        if (!error.message.includes('Session expired')) {
            showToast(error.isNetworkError
                ? 'Server unreachable — retrying automatically...'
                : 'Failed to load dashboard stats', 'error');
        }
    }

    try {
        const chartData = await fetchWithRetry('/api/dashboard/response-times');
        renderChart(chartData.series);
        chartOk = true;
    } catch (error) {
        console.error('Failed to load chart data:', error);
        // Only show chart error if stats also failed (avoid double toasts)
        if (!statsOk && !error.message.includes('Session expired')) {
            showToast('Failed to load chart data', 'error');
        }
    }

    if (statsOk || chartOk) {
        updateLastRefreshed();
    }
}

async function refreshChartOnly() {
    try {
        const chartData = await apiRequest('/api/dashboard/response-times');
        renderChart(chartData.series);
        updateLastRefreshed();
    } catch (error) {
        console.error('Chart refresh failed:', error);
    }
}

function updateLastRefreshed() {
    const el = document.getElementById('last-refreshed');
    if (el) {
        const now = new Date();
        el.textContent = `Last updated: ${now.toLocaleTimeString()}`;
    }
    // Pulse the live indicator
    const dot = document.getElementById('live-dot');
    if (dot) {
        dot.classList.remove('pulse');
        void dot.offsetWidth; // force reflow
        dot.classList.add('pulse');
    }
}

// ---- Render Stats Cards ----
function renderStats(stats) {
    const grid = document.getElementById('stats-grid');
    if (!grid) return;

    grid.innerHTML = `
        <div class="stat-card">
            <div class="stat-icon">📡</div>
            <div class="stat-value">${stats.total_apis}</div>
            <div class="stat-label">Total APIs</div>
        </div>
        <div class="stat-card">
            <div class="stat-icon">✅</div>
            <div class="stat-value">${stats.active_apis}</div>
            <div class="stat-label">Active APIs</div>
        </div>
        <div class="stat-card">
            <div class="stat-icon">🔴</div>
            <div class="stat-value">${stats.down_apis}</div>
            <div class="stat-label">Down APIs</div>
        </div>
        <div class="stat-card">
            <div class="stat-icon">⚡</div>
            <div class="stat-value">${stats.avg_response_time}<small style="font-size:0.5em;color:var(--text-secondary)">ms</small></div>
            <div class="stat-label">Avg Response Time</div>
        </div>
        <div class="stat-card">
            <div class="stat-icon">📈</div>
            <div class="stat-value">${stats.uptime_percentage}<small style="font-size:0.5em;color:var(--text-secondary)">%</small></div>
            <div class="stat-label">Uptime</div>
        </div>
        <div class="stat-card">
            <div class="stat-icon">⚠️</div>
            <div class="stat-value">${stats.error_rate}<small style="font-size:0.5em;color:var(--text-secondary)">%</small></div>
            <div class="stat-label">Error Rate</div>
        </div>
    `;
}

// ---- Render Endpoints Table ----
function renderEndpoints(endpoints) {
    const tbody = document.getElementById('endpoints-tbody');
    if (!tbody) return;

    if (!endpoints || endpoints.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="7">
                    <div class="empty-state">
                        <div class="empty-icon">📡</div>
                        <h3>No API endpoints yet</h3>
                        <p>Add your first API endpoint to start monitoring.</p>
                    </div>
                </td>
            </tr>
        `;
        return;
    }

    const user = getUser();
    const isCompany = user && user.role === 'company';

    tbody.innerHTML = endpoints.map(ep => {
        const statusBadge = ep.is_down
            ? '<span class="badge badge-danger"><span class="dot"></span> Down</span>'
            : ep.is_active
                ? '<span class="badge badge-success"><span class="dot"></span> Active</span>'
                : '<span class="badge badge-neutral">Paused</span>';

        const responseTime = ep.last_response_time !== null
            ? `${ep.last_response_time}ms`
            : '—';

        const lastCheck = ep.last_check
            ? new Date(ep.last_check).toLocaleTimeString()
            : 'Never';

        const actionButtons = isCompany ? `
            <td>
                <div class="action-btns">
                    <button class="action-btn" onclick="openEditModal('${ep.id}')" title="Edit">✏️</button>
                    <button class="action-btn delete" onclick="deleteEndpoint('${ep.id}', '${escapeHtml(ep.name)}')" title="Delete">🗑️</button>
                </div>
            </td>
        ` : '<td></td>';

        return `
            <tr>
                <td>
                    <strong>${escapeHtml(ep.name)}</strong>
                    <br><span style="color:var(--text-muted);font-size:0.8rem">${escapeHtml(truncateUrl(ep.url))}</span>
                </td>
                <td><span class="method-badge method-${ep.method}">${ep.method}</span></td>
                <td>${statusBadge}</td>
                <td>${responseTime}</td>
                <td style="color:var(--text-secondary)">${lastCheck}</td>
                <td>
                    <label class="toggle" title="${ep.is_active ? 'Disable' : 'Enable'} monitoring">
                        <input type="checkbox" ${ep.is_active ? 'checked' : ''} onchange="toggleEndpoint('${ep.id}')" ${!isCompany ? 'disabled' : ''}>
                        <span class="toggle-slider"></span>
                    </label>
                </td>
                ${actionButtons}
            </tr>
        `;
    }).join('');
}

// ---- Response Time Chart ----
function renderChart(series) {
    const canvas = document.getElementById('response-chart');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');

    const colors = [
        { line: '#6366f1', bg: 'rgba(99,102,241,0.1)' },
        { line: '#06b6d4', bg: 'rgba(6,182,212,0.1)' },
        { line: '#10b981', bg: 'rgba(16,185,129,0.1)' },
        { line: '#f59e0b', bg: 'rgba(245,158,11,0.1)' },
        { line: '#ef4444', bg: 'rgba(239,68,68,0.1)' },
        { line: '#8b5cf6', bg: 'rgba(139,92,246,0.1)' },
    ];

    const datasets = (series || []).map((s, i) => {
        const color = colors[i % colors.length];
        return {
            label: s.name,
            data: s.data.map(d => ({
                x: new Date(d.time),
                y: d.response_time,
            })),
            borderColor: color.line,
            backgroundColor: color.bg,
            fill: true,
            tension: 0.4,
            borderWidth: 2,
            pointRadius: 2,
            pointHoverRadius: 5,
        };
    });

    if (responseChart) {
        responseChart.data.datasets = datasets;
        responseChart.update('default');
        return;
    }

    responseChart = new Chart(ctx, {
        type: 'line',
        data: { datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            plugins: {
                legend: {
                    labels: {
                        color: '#94a3b8',
                        font: { family: 'Inter', size: 12 },
                        usePointStyle: true,
                        pointStyle: 'circle',
                    },
                },
                tooltip: {
                    backgroundColor: '#1e293b',
                    titleColor: '#f1f5f9',
                    bodyColor: '#94a3b8',
                    borderColor: 'rgba(148,163,184,0.2)',
                    borderWidth: 1,
                    padding: 12,
                    callbacks: {
                        label: (ctx) => `${ctx.dataset.label}: ${ctx.parsed.y}ms`,
                    },
                },
            },
            scales: {
                x: {
                    type: 'time',
                    time: {
                        unit: 'hour',
                        displayFormats: { hour: 'HH:mm' },
                    },
                    grid: { color: 'rgba(148,163,184,0.08)' },
                    ticks: { color: '#64748b', font: { size: 11 } },
                },
                y: {
                    beginAtZero: true,
                    grid: { color: 'rgba(148,163,184,0.08)' },
                    ticks: {
                        color: '#64748b',
                        font: { size: 11 },
                        callback: (v) => `${v}ms`,
                    },
                },
            },
            animation: {
                duration: 800,
                easing: 'easeInOutQuart',
            },
        },
    });
}

// ---- Modal: Add Endpoint ----
function openAddModal() {
    document.getElementById('endpoint-form').reset();
    document.getElementById('add-modal').classList.remove('hidden');
}

function closeModal() {
    document.getElementById('add-modal').classList.add('hidden');
}

async function handleEndpointSubmit(e) {
    e.preventDefault();
    const btn = e.target.querySelector('button[type="submit"]');
    btn.disabled = true;
    btn.innerHTML = '<div class="spinner"></div> Saving...';

    try {
        await apiRequest('/api/endpoints', {
            method: 'POST',
            body: {
                name: document.getElementById('ep-name').value,
                url: document.getElementById('ep-url').value,
                method: document.getElementById('ep-method').value,
                interval: parseInt(document.getElementById('ep-interval').value),
            },
        });

        showToast('Endpoint added successfully!');
        closeModal();
        loadDashboardData();
    } catch (error) {
        showToast(error.message, 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = 'Add Endpoint';
    }
}

// ---- Modal: Edit Endpoint ----
let currentEditId = null;

async function openEditModal(endpointId) {
    currentEditId = endpointId;
    try {
        const data = await apiRequest(`/api/endpoints/${endpointId}`);
        const ep = data.endpoint;

        document.getElementById('edit-ep-name').value = ep.name;
        document.getElementById('edit-ep-url').value = ep.url;
        document.getElementById('edit-ep-method').value = ep.method;
        document.getElementById('edit-ep-interval').value = ep.interval;

        document.getElementById('edit-modal').classList.remove('hidden');
    } catch (error) {
        showToast(error.message, 'error');
    }
}

function closeEditModal() {
    document.getElementById('edit-modal').classList.add('hidden');
    currentEditId = null;
}

async function handleEditSubmit(e) {
    e.preventDefault();
    if (!currentEditId) return;

    const btn = e.target.querySelector('button[type="submit"]');
    btn.disabled = true;
    btn.innerHTML = '<div class="spinner"></div> Saving...';

    try {
        await apiRequest(`/api/endpoints/${currentEditId}`, {
            method: 'PUT',
            body: {
                name: document.getElementById('edit-ep-name').value,
                url: document.getElementById('edit-ep-url').value,
                method: document.getElementById('edit-ep-method').value,
                interval: parseInt(document.getElementById('edit-ep-interval').value),
            },
        });

        showToast('Endpoint updated successfully!');
        closeEditModal();
        loadDashboardData();
    } catch (error) {
        showToast(error.message, 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = 'Save Changes';
    }
}

// ---- Endpoint Actions ----
async function toggleEndpoint(endpointId) {
    try {
        const data = await apiRequest(`/api/endpoints/${endpointId}/toggle`, {
            method: 'PATCH',
        });
        showToast(data.message);
        loadDashboardData();
    } catch (error) {
        showToast(error.message, 'error');
        loadDashboardData();
    }
}

async function deleteEndpoint(endpointId, name) {
    if (!confirm(`Delete "${name}"? This will remove all monitoring logs for this endpoint.`)) {
        return;
    }

    try {
        await apiRequest(`/api/endpoints/${endpointId}`, { method: 'DELETE' });
        showToast('Endpoint deleted');
        loadDashboardData();
    } catch (error) {
        showToast(error.message, 'error');
    }
}

// ===========================
// Employee Management (Company only)
// ===========================

async function loadEmployees() {
    try {
        const data = await apiRequest('/api/auth/employees');
        renderEmployees(data.employees, data.pending_invites);
    } catch (error) {
        console.error('Failed to load employees:', error);
    }
}

function renderEmployees(employees, pendingInvites) {
    const tbody = document.getElementById('employees-tbody');
    if (!tbody) return;

    const allRows = [];

    // Active employees
    if (employees && employees.length > 0) {
        employees.forEach(emp => {
            allRows.push(`
                <tr>
                    <td><strong>${escapeHtml(emp.name)}</strong></td>
                    <td style="color:var(--text-secondary)">${escapeHtml(emp.email)}</td>
                    <td><span class="credential-id" style="font-family:monospace;color:var(--accent-secondary);font-weight:600;">${escapeHtml(emp.employee_id)}</span></td>
                    <td><span class="badge badge-success">Active</span></td>
                    <td style="color:var(--text-secondary)">${emp.created_at ? new Date(emp.created_at).toLocaleDateString() : '—'}</td>
                </tr>
            `);
        });
    }

    // Pending invitations
    if (pendingInvites && pendingInvites.length > 0) {
        pendingInvites.forEach(inv => {
            allRows.push(`
                <tr>
                    <td><strong>${escapeHtml(inv.name)}</strong></td>
                    <td style="color:var(--text-secondary)">${escapeHtml(inv.email)}</td>
                    <td style="color:var(--text-muted)">—</td>
                    <td><span class="badge badge-warning">Pending</span></td>
                    <td style="color:var(--text-secondary)">${inv.created_at ? new Date(inv.created_at).toLocaleDateString() : '—'}</td>
                </tr>
            `);
        });
    }

    if (allRows.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="5" style="text-align:center;padding:24px;color:var(--text-muted);">
                    <div style="font-size:2rem;margin-bottom:8px;">👥</div>
                    No employees yet. Use the form above to invite your first employee.
                </td>
            </tr>
        `;
    } else {
        tbody.innerHTML = allRows.join('');
    }
}

async function handleInviteEmployee(e) {
    e.preventDefault();
    const btn = document.getElementById('invite-btn');
    btn.disabled = true;
    btn.innerHTML = '<div class="spinner"></div> Sending...';

    try {
        const data = await apiRequest('/api/auth/invite-employee', {
            method: 'POST',
            body: {
                name: document.getElementById('invite-name').value,
                email: document.getElementById('invite-email').value,
            },
        });

        showToast(data.message);

        // If SMTP not configured, show the dev token link
        if (!data.email_sent) {
            showToast('Check the server console for the invite link', 'warning', 6000);
        }

        document.getElementById('invite-employee-form').reset();
        loadEmployees();
    } catch (error) {
        showToast(error.message, 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '📧 Send Invite';
    }
}

// ---- Utilities ----
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function truncateUrl(url) {
    try {
        const u = new URL(url);
        const display = u.hostname + u.pathname;
        return display.length > 45 ? display.slice(0, 42) + '...' : display;
    } catch {
        return url.length > 45 ? url.slice(0, 42) + '...' : url;
    }
}

// ---- Init on load ----
document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('stats-grid')) {
        initDashboard();
    }
});
