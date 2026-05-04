'use strict';

let _dashRefreshInterval   = null;
let _dashChartAutoRefresh  = null;

/* ─────────────────────────────────────────────────────────── */
/* Init                                                         */
/* ─────────────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
    initDashboard();
});

function initDashboard() {
    if (!isAuthenticated()) {
        window.location.href = 'login.html';
        return;
    }

    setupNavbar();
    loadDashboardData();                                    // stats + monitor cards

    // Charts: wait for charts.js DOMContentLoaded to finish, then fetch
    setTimeout(() => {
        if (window.initChartWithDefaults) initChartWithDefaults();
    }, 200);

    // Range selector change listener
    const rangeSelector = document.getElementById('stats-range-selector');
    if (rangeSelector) {
        rangeSelector.addEventListener('change', () => {
            loadDashboardData();
            if (window.initChartWithDefaults) initChartWithDefaults();
        });
    }

    // Auto-refresh stats & monitor list every 30s
    _dashRefreshInterval = setInterval(loadDashboardData, 30000);

    // Auto-refresh charts every 60s (uses current time-picker window)
    _dashChartAutoRefresh = setInterval(() => {
        if (window.initChartWithDefaults) initChartWithDefaults();
    }, 60000);
}

/* ─────────────────────────────────────────────────────────── */
/* Navbar                                                       */
/* ─────────────────────────────────────────────────────────── */
function setupNavbar() {
    const user = getUser();
    if (!user) return;

    document.querySelectorAll('.user-name, #user-name').forEach(el => el.textContent = user.name);
    document.querySelectorAll('.user-avatar-small, .user-avatar, #user-avatar').forEach(el => el.textContent = user.name.charAt(0).toUpperCase());
    document.querySelectorAll('.user-role').forEach(el => el.textContent = user.role === 'company' ? 'Company' : 'Employee');

    document.querySelectorAll('[data-role]').forEach(el => {
        const allowed = el.dataset.role;
        if (allowed && allowed !== user.role) el.style.display = 'none';
    });

    const topBarRight = document.querySelector('.topbar-right');
    if (topBarRight && !document.getElementById('logout-btn')) {
        const btn = document.createElement('button');
        btn.id        = 'logout-btn';
        btn.className = 'btn btn-secondary btn-sm';
        btn.style.marginRight = '1rem';
        btn.innerHTML = '<i class="fa-solid fa-right-from-bracket"></i> Logout';
        btn.onclick   = logout;
        topBarRight.insertBefore(btn, topBarRight.firstChild);
    }
}

/* ─────────────────────────────────────────────────────────── */
/* Dashboard data (stats + endpoints list)                      */
/* ─────────────────────────────────────────────────────────── */
window.loadDashboardData = async function () {
    try {
        const rangeSelector = document.getElementById('stats-range-selector');
        const range = rangeSelector ? rangeSelector.value : '1d';
        
        const statsData = await apiRequest(`/api/dashboard/stats?range=${range}`);
        renderStats(statsData.stats || {});
        // dashboard.html renders cards via renderMonitorCards() which is in the
        // inline <script> block. Pass the endpoints array there via a custom event.
        document.dispatchEvent(new CustomEvent('endpointsReady', { detail: { endpoints: statsData.endpoints || [] } }));
    } catch (err) {
        console.error('Failed to load dashboard stats:', err);
        // Dispatch empty array to prevent UI hanging in "Loading" state
        document.dispatchEvent(new CustomEvent('endpointsReady', { detail: { endpoints: [] } }));
    }
};

/* ─────────────────────────────────────────────────────────── */
/* Stats rendering                                              */
/* ─────────────────────────────────────────────────────────── */
function renderStats(stats) {
    const set = (id, html) => { const el = document.getElementById(id); if (el) el.innerHTML = html; };

    set('stat-total',    stats.total_apis   ?? 0);
    set('stat-active',   stats.active_apis  ?? 0);
    set('stat-down',     stats.down_apis    ?? 0);
    set('stat-response', stats.avg_response_time != null
        ? `${stats.avg_response_time}<span class="text-muted" style="font-size:0.875rem">ms</span>`
        : '—');
    set('stat-uptime',   stats.uptime_percentage != null
        ? `${stats.uptime_percentage}<span class="text-muted" style="font-size:0.875rem">%</span>`
        : '—');
    set('stat-alerts',   stats.down_apis ?? 0);
}

/* ─────────────────────────────────────────────────────────── */
/* Legacy compat — chart dispatch (still used by endpoint-detail) */
/* ─────────────────────────────────────────────────────────── */
function renderChartData(series) {
    document.dispatchEvent(new CustomEvent('chartDataReady', { detail: { series } }));
}
