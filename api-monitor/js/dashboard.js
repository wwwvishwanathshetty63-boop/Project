let responseChart = null;
let refreshInterval = null;
let chartRefreshInterval = null;

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    initDashboard();
});

function initDashboard() {
    if (!isAuthenticated()) {
        window.location.href = 'login.html';
        return;
    }

    setupNavbar();
    loadDashboardData();

    // Auto-refresh stats & endpoints every 30 seconds
    refreshInterval = setInterval(loadDashboardData, 30000);

    // Real-time chart refresh every 10 seconds
    chartRefreshInterval = setInterval(refreshChartOnly, 10000);
}

function setupNavbar() {
    const user = getUser();
    if (!user) return;

    // The new UI has different IDs, let's find them if they exist
    const userNameElements = document.querySelectorAll('.user-name, #user-name');
    const avatarElements = document.querySelectorAll('.user-avatar-small, .user-avatar, #user-avatar');

    userNameElements.forEach(el => el.textContent = user.name);
    avatarElements.forEach(el => el.textContent = user.name.charAt(0).toUpperCase());

    // Setup logout if there is a button (add one if needed to the top navbar)
    const topBarRight = document.querySelector('.topbar-right');
    if (topBarRight && !document.getElementById('logout-btn')) {
        const logoutBtn = document.createElement('button');
        logoutBtn.id = 'logout-btn';
        logoutBtn.className = 'btn btn-secondary btn-sm';
        logoutBtn.style.marginRight = '1rem';
        logoutBtn.innerHTML = '<i class="fa-solid fa-right-from-bracket"></i> Logout';
        logoutBtn.onclick = logout;
        topBarRight.insertBefore(logoutBtn, topBarRight.firstChild);
    }
}

// fetchWithRetry is now centrally located in app.js
async function loadDashboardData() {
    try {
        const statsData = await fetchWithRetry('/api/dashboard/stats');
        renderStats(statsData.stats);
        renderRecentEndpoints(statsData.endpoints);
    } catch (error) {
        console.error('Failed to load stats:', error);
    }

    try {
        const chartData = await fetchWithRetry('/api/dashboard/response-times');
        renderChartData(chartData.series);
    } catch (error) {
        console.error('Failed to load chart data:', error);
    }
}

async function refreshChartOnly() {
    try {
        const chartData = await apiRequest('/api/dashboard/response-times');
        renderChartData(chartData.series);
    } catch (error) {
        console.error('Chart refresh failed:', error);
    }
}

function renderStats(stats) {
    const cards = document.querySelectorAll('.stat-card');
    if (cards.length >= 6) {
        // We know the order from index.html: Total, Active, Down, Avg Time, Uptime, Alerts
        cards[0].querySelector('.stat-value').textContent = stats.total_apis;
        cards[1].querySelector('.stat-value').textContent = stats.active_apis;
        cards[2].querySelector('.stat-value').textContent = stats.down_apis;
        cards[3].querySelector('.stat-value').innerHTML = `${stats.avg_response_time}<span class="text-muted" style="font-size: 0.875rem;">ms</span>`;
        cards[4].querySelector('.stat-value').innerHTML = `${stats.uptime_percentage}<span class="text-muted" style="font-size: 0.875rem;">%</span>`;
        cards[5].querySelector('.stat-value').textContent = stats.error_rate > 0 ? '1' : '0'; // Placeholder for alerts based on error rate
    }
}

function renderRecentEndpoints(endpoints) {
    const tbody = document.querySelector('#recent-api-table tbody');
    if (!tbody) return;

    if (!endpoints || endpoints.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" class="text-center text-muted">No endpoints monitored yet.</td></tr>`;
        return;
    }

    // Only show top 5 for the recent table
    const recent = endpoints.slice(0, 5);

    tbody.innerHTML = recent.map(api => {
        let statusHtml = '';
        if (api.is_down) {
            statusHtml = `<span class="badge badge-danger"><span class="badge-dot"></span> Down</span>`;
        } else if (api.is_active) {
            statusHtml = `<span class="badge badge-success"><span class="badge-dot"></span> Active</span>`;
        } else {
            statusHtml = `<span class="badge badge-neutral">Paused</span>`;
        }

        const responseTime = api.last_response_time !== null ? `${api.last_response_time}ms` : '—';
        const lastChecked = api.last_check ? new Date(api.last_check).toLocaleString() : 'Never';

        return `
            <tr>
                <td style="font-weight: 500;">${escapeHtml(api.name)}</td>
                <td><span class="code-style">${escapeHtml(api.url)}</span></td>
                <td>${statusHtml}</td>
                <td style="color: ${api.is_down ? 'var(--text-muted)' : 'inherit'}">${responseTime}</td>
                <td style="color: var(--text-muted);">${lastChecked}</td>
            </tr>
        `;
    }).join('');
}

// Hook into charts.js functions
function renderChartData(series) {
    // This will be handled by a global event or by exporting a function from charts.js
    // For now, dispatch an event that charts.js can listen to
    const event = new CustomEvent('chartDataReady', { detail: { series: series, uptime: null } });
    document.dispatchEvent(event);
}

// Utility
// escapeHtml is now centralized in app.js
