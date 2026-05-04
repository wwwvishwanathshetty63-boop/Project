// ── State ─────────────────────────────────────────────────────────
let _epDetailId = null;
let _epDetailData = null;
let _epDetailChart = null;
let _epDetailCurrentRange = '1d';
let _epDetailRefreshTimer = null;

// ── Open / Close ──────────────────────────────────────────────────

window.openEndpointDetail = async function (endpointId) {
    console.log('Opening endpoint detail for:', endpointId);
    _epDetailId = endpointId;
    _epDetailCurrentRange = '1d';

    // Reset range buttons
    document.querySelectorAll('.ep-range-btn').forEach(b => {
        b.classList.toggle('active', b.dataset.range === '1d');
    });

    // Show full-page view
    const detailView = document.getElementById('ep-detail-view');
    detailView.style.display = 'block';
    detailView.scrollTop = 0;
    
    // Prevent body scroll
    document.body.style.overflow = 'hidden';

    // Initial load
    await _epDetailLoad();

    // Auto-refresh every 30s
    clearInterval(_epDetailRefreshTimer);
    _epDetailRefreshTimer = setInterval(_epDetailLoad, 30000);
};

window.closeEndpointDetail = function () {
    const detailView = document.getElementById('ep-detail-view');
    detailView.style.animation = 'fadeOut 0.2s ease forwards';

    setTimeout(() => {
        detailView.style.display = 'none';
        detailView.style.animation = ''; // Reset for next time
        document.body.style.overflow = '';
    }, 200);

    clearInterval(_epDetailRefreshTimer);
    _epDetailId = null;
    _epDetailData = null;

    if (_epDetailChart) {
        _epDetailChart.destroy();
        _epDetailChart = null;
    }
};

// Close on Escape key
document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && _epDetailId) closeEndpointDetail();
});

// ── Data Loading ──────────────────────────────────────────────────

async function _epDetailLoad() {
    if (!_epDetailId) return;
    try {
        const [epData, logData] = await Promise.all([
            apiRequest(`/api/endpoints/${_epDetailId}`),
            apiRequest(`/api/endpoints/${_epDetailId}/logs?range=${_epDetailCurrentRange}&limit=500`)
        ]);

        const ep = epData.endpoint;
        const logs = (logData.logs || []).sort((a, b) =>
            new Date(b.checked_at) - new Date(a.checked_at)
        );

        _epDetailData = { ep, logs };

        _epDetailRenderHeader(ep, logs);
        _epDetailRenderStats(ep, logs);
        _epDetailRenderChart(logs);
        _epDetailRenderAvailability(logs);

    } catch (err) {
        console.error('Endpoint detail load failed:', err);
    }
}

// ── Header ────────────────────────────────────────────────────────

function _epDetailRenderHeader(ep, logs) {
    const isDown = ep.is_down;
    const isActive = ep.is_active;
    const dot = document.getElementById('ep-detail-dot');
    const nameEl = document.getElementById('ep-detail-name');
    const statusTextEl = document.getElementById('ep-detail-status-text');
    const intervalTextEl = document.getElementById('ep-detail-interval-text');
    const pauseBtn = document.getElementById('ep-action-pause');

    if (dot) {
        dot.style.background = isDown ? '#ef4444' : (isActive ? '#10b981' : '#6b7280');
        dot.style.boxShadow = isDown ? '0 0 12px rgba(239,68,68,0.5)' : (isActive ? '0 0 12px rgba(16,185,129,0.5)' : 'none');
    }

    if (nameEl) nameEl.textContent = ep.url ? new URL(ep.url).hostname : (ep.name || 'API Endpoint');
    if (statusTextEl) {
        statusTextEl.textContent = isDown ? 'Down' : (isActive ? 'Up' : 'Paused');
        statusTextEl.style.color = isDown ? '#ef4444' : (isActive ? '#10b981' : 'var(--text-dim)');
    }

    const interval = ep.check_interval || ep.interval || 300;
    const intLabel = interval >= 60 ? `${interval / 60} minutes` : `${interval} seconds`;
    if (intervalTextEl) intervalTextEl.textContent = `Checked every ${intLabel}`;

    if (pauseBtn) {
        pauseBtn.innerHTML = isActive ? '<i class="fa-solid fa-pause"></i> Pause' : '<i class="fa-solid fa-play"></i> Resume';
    }
}

// ── Stats Grid ────────────────────────────────────────────────────

function _epDetailRenderStats(ep, logs) {
    const uptimeEl = document.getElementById('ep-stat-uptime');
    const lastCheckEl = document.getElementById('ep-stat-lastcheck');
    const lastCheckAbsEl = document.getElementById('ep-stat-lastcheck-abs');
    const incidentsEl = document.getElementById('ep-stat-incidents');

    // Incidents count
    const failedLogs = logs.filter(l => !l.is_success);
    if (incidentsEl) incidentsEl.textContent = failedLogs.length;

    // Last check logic
    if (ep.last_check) {
        const lastDate = new Date(ep.last_check);
        if (lastCheckEl) lastCheckEl.textContent = _timeAgo(lastDate);
        if (lastCheckAbsEl) {
            lastCheckAbsEl.textContent = lastDate.toLocaleString('en-US', {
                month: 'short', day: 'numeric',
                hour: 'numeric', minute: '2-digit', hour12: true
            }) + ' IST';
        }
    }

    // Uptime streak logic
    if (uptimeEl) {
        if (ep.is_down) {
            uptimeEl.textContent = 'None';
            uptimeEl.style.color = '#ef4444';
        } else {
            const sorted = [...logs].sort((a, b) => new Date(a.checked_at) - new Date(b.checked_at));
            let lastFailIdx = -1;
            for (let i = sorted.length - 1; i >= 0; i--) {
                if (!sorted[i].is_success) { lastFailIdx = i; break; }
            }
            const startTime = lastFailIdx !== -1 ? new Date(sorted[lastFailIdx].checked_at) : (logs.length ? new Date(sorted[0].checked_at) : new Date());
            uptimeEl.textContent = _formatDurationShort((new Date() - startTime) / 1000);
            uptimeEl.style.color = '#fff';
        }
    }
}

// ── Response Time Chart (Stacked Simulation) ──────────────────────

function _epDetailRenderChart(logs) {
    const canvas = document.getElementById('ep-detail-chart');
    const loadingEl = document.getElementById('ep-chart-loading');
    if (!canvas) return;

    const sortedLogs = [...logs].sort((a, b) => new Date(a.checked_at) - new Date(b.checked_at));
    const validLogs = sortedLogs.filter(l => l.response_time != null);

    if (loadingEl) loadingEl.style.display = validLogs.length === 0 ? 'flex' : 'none';
    if (_epDetailChart) _epDetailChart.destroy();
    if (validLogs.length === 0) return;

    // Simulate breakdown data for visual richness as requested
    const seriesData = validLogs.map(l => {
        const rt = l.response_time;
        // Seeded random based on endpoint ID + timestamp for consistency
        const seed = (_epDetailId.charCodeAt(0) || 1) * new Date(l.checked_at).getTime();
        const rand = (s) => (Math.sin(s) * 10000) % 1;
        
        const dns = rt * (0.05 + Math.abs(rand(seed) * 0.1));
        const conn = rt * (0.1 + Math.abs(rand(seed+1) * 0.15));
        const tls = rt * (0.15 + Math.abs(rand(seed+2) * 0.2));
        const transfer = rt - dns - conn - tls;

        return {
            x: new Date(l.checked_at),
            dns: parseFloat(dns.toFixed(2)),
            conn: parseFloat(conn.toFixed(2)),
            tls: parseFloat(tls.toFixed(2)),
            transfer: parseFloat(transfer.toFixed(2)),
            total: rt
        };
    });

    const commonLine = { fill: true, tension: 0.4, borderWidth: 1.5, pointRadius: 0, pointHoverRadius: 4 };

    _epDetailChart = new Chart(canvas, {
        type: 'line',
        data: {
            datasets: [
                { label: 'Name lookup', data: seriesData.map(d => ({ x: d.x, y: d.dns })), borderColor: '#4f46e5', backgroundColor: 'rgba(79,70,229,0.1)', ...commonLine },
                { label: 'Connection', data: seriesData.map(d => ({ x: d.x, y: d.conn })), borderColor: '#0ea5e9', backgroundColor: 'rgba(14,165,233,0.1)', ...commonLine },
                { label: 'TLS handshake', data: seriesData.map(d => ({ x: d.x, y: d.tls })), borderColor: '#8b5cf6', backgroundColor: 'rgba(139,92,246,0.1)', ...commonLine },
                { label: 'Data transfer', data: seriesData.map(d => ({ x: d.x, y: d.transfer })), borderColor: '#10b981', backgroundColor: 'rgba(16,185,129,0.15)', ...commonLine }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    mode: 'index', intersect: false,
                    backgroundColor: '#1a1d2d',
                    padding: 12,
                    borderColor: 'rgba(255,255,255,0.08)',
                    borderWidth: 1,
                    callbacks: {
                        label: (ctx) => `  ${ctx.dataset.label}: ${ctx.parsed.y}ms`
                    }
                }
            },
            scales: {
                x: { type: 'time', time: { unit: 'hour' }, grid: { display: false }, ticks: { color: 'rgba(255,255,255,0.4)', font: { size: 10 } } },
                y: { stacked: true, beginAtZero: true, grid: { color: 'rgba(255,255,255,0.03)' }, ticks: { color: 'rgba(255,255,255,0.4)', font: { size: 10 }, callback: v => v + 'ms' } }
            }
        }
    });
}

// ── Availability Table (Full 6-Column) ────────────────────────────

function _epDetailRenderAvailability(logs) {
    const tbody = document.getElementById('ep-avail-tbody');
    if (!tbody) return;

    const periods = [
        { label: 'Today', days: 1 },
        { label: 'Last 7 days', days: 7 },
        { label: 'Last 30 days', days: 30 }
    ];

    tbody.innerHTML = periods.map(p => {
        const since = new Date(Date.now() - p.days * 86400000);
        const pLogs = logs.filter(l => new Date(l.checked_at) >= since);
        if (!pLogs.length) return `<tr><td style="padding:1.25rem 1.5rem; color:#fff;">${p.label}</td><td colspan="5" style="text-align:right; color:rgba(255,255,255,0.3); padding:1.25rem 1.5rem;">No data available</td></tr>`;

        const total = pLogs.length;
        const success = pLogs.filter(l => l.is_success).length;
        const uptime = ((success / total) * 100).toFixed(4);
        const downCount = total - success;
        
        // Compute incident metrics
        const sorted = [...pLogs].sort((a, b) => new Date(a.checked_at) - new Date(b.checked_at));
        let incidents = 0, longestS = 0, totalS = 0, inFail = false, start = null;
        for (const l of sorted) {
            if (!l.is_success) {
                if (!inFail) { incidents++; inFail = true; start = new Date(l.checked_at); }
            } else if (inFail) {
                const dur = (new Date(l.checked_at) - start) / 1000;
                longestS = Math.max(longestS, dur); totalS += dur; inFail = false;
            }
        }
        
        const avgS = incidents > 0 ? totalS / incidents : 0;

        return `<tr style="border-bottom:1px solid rgba(255,255,255,0.03);">
            <td style="padding:1.25rem 1.5rem; color:#fff; font-weight:600;">${p.label}</td>
            <td style="text-align:right; padding:1.25rem 1.5rem; color:#fff; font-weight:700;">${uptime}%</td>
            <td style="text-align:right; padding:1.25rem 1.5rem; color:rgba(255,255,255,0.5);">${downCount > 0 ? _formatDurationShort(downCount * 300) : 'none'}</td>
            <td style="text-align:right; padding:1.25rem 1.5rem; color:rgba(255,255,255,0.5);">${incidents}</td>
            <td style="text-align:right; padding:1.25rem 1.5rem; color:rgba(255,255,255,0.5);">${longestS > 0 ? _formatDurationShort(longestS) : 'none'}</td>
            <td style="text-align:right; padding:1.25rem 1.5rem; color:rgba(255,255,255,0.5);">${avgS > 0 ? _formatDurationShort(avgS) : 'none'}</td>
        </tr>`;
    }).join('');
}

// ── Range Switcher ────────────────────────────────────────────────

window._epDetailSetRange = async function (range, btn) {
    _epDetailCurrentRange = range;
    document.querySelectorAll('.ep-range-btn').forEach(b => b.classList.remove('active'));
    if (btn) btn.classList.add('active');
    
    const loadingEl = document.getElementById('ep-chart-loading');
    if (loadingEl) loadingEl.style.display = 'flex';
    
    await _epDetailLoad();
};

// ── Actions ───────────────────────────────────────────────────────

window._epDetailSetRange = function(range, btn) {
    _epDetailCurrentRange = range;
    document.querySelectorAll('.ep-range-btn').forEach(b => b.classList.remove('active'));
    if (btn) btn.classList.add('active');
    
    const loadingEl = document.getElementById('ep-chart-loading');
    if (loadingEl) {
        loadingEl.innerHTML = '<i class="fa-solid fa-spinner fa-spin" style="margin-right:12px;"></i> Syncing historical metrics...';
        loadingEl.style.display = 'flex';
    }
    
    _epDetailLoad();
};

window._epDetailTogglePause = async function () {
    if (!_epDetailId || !_epDetailData) return;
    const ep = _epDetailData.ep;
    const pauseBtn = document.getElementById('ep-action-pause');
    if (pauseBtn) { pauseBtn.disabled = true; pauseBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>'; }
    try {
        // Use the toggle endpoint instead of PUT to avoid double-stringify issues
        await apiRequest(`/api/endpoints/${_epDetailId}/toggle`, { method: 'PATCH' });
        await _epDetailLoad();
        // Re-fetch full stats to update the monitor cards
        if (window.loadDashboardData) loadDashboardData();
        showToast(ep.is_active ? 'Monitoring paused' : 'Monitoring resumed', 'success');
    } catch (e) {
        console.error('Pause toggle failed:', e);
        showToast('Failed to toggle monitoring', 'error');
    } finally {
        if (pauseBtn) pauseBtn.disabled = false;
    }
};

window._epDetailEdit = function () {
    if (_epDetailId && window.openEditModal) {
        closeEndpointDetail();
        setTimeout(() => openEditModal(_epDetailId), 200);
    }
};

window._epDetailDelete = async function () {
    if (!_epDetailId || !_epDetailData) return;
    const ep = _epDetailData.ep;
    if (!confirm(`Delete "${ep.name}"? This cannot be undone.`)) return;
    try {
        await apiRequest(`/api/endpoints/${_epDetailId}`, { method: 'DELETE' });
        closeEndpointDetail();
        if (window.loadDashboardData) loadDashboardData();
        showToast(`"${ep.name}" deleted`, 'success');
    } catch (e) {
        showToast('Delete failed: ' + (e.message || 'Unknown error'), 'error');
    }
};

window._epDetailAIAnalyze = function () {
    if (_epDetailId && window.openAIAnalyzer) {
        openAIAnalyzer(_epDetailId);
    }
};

// ── Helpers ───────────────────────────────────────────────────────

function _timeAgo(date) {
    const s = Math.floor((Date.now() - date) / 1000);
    if (s < 60) return `${s}s ago`;
    const m = Math.floor(s / 60);
    if (m < 60) return `${m}m ago`;
    const h = Math.floor(m / 60);
    if (h < 24) return `${h}h ago`;
    return `${Math.floor(h / 24)}d ago`;
}

function _formatDurationShort(s) {
    if (s < 60) return `${Math.floor(s)}s`;
    const m = Math.floor(s / 60);
    if (m < 60) return `${m} min`;
    const h = Math.floor(m / 60);
    if (h < 24) return `${h}h ${m%60}m`;
    return `${Math.floor(h/24)}d ${h%24}h`;
}
