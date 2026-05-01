/**
 * AI Analyzer Module — Smart Downtime Diagnostics
 * Analyzes down API endpoints and provides root-cause analysis + recommendations.
 */

// ── AI Analysis Engine ─────────────────────────────────────────

/**
 * Generate a comprehensive downtime analysis based on endpoint data.
 * This uses intelligent pattern-matching on HTTP status codes, response times,
 * uptime history and URL patterns to produce a detailed diagnosis.
 */
function generateAIAnalysis(endpoint) {
    const statusCode = endpoint.last_status_code || null;
    const responseTime = endpoint.last_response_time || null;
    const uptime = endpoint.uptime_percentage != null ? endpoint.uptime_percentage : null;
    const url = endpoint.url || '';
    const method = (endpoint.method || 'GET').toUpperCase();
    const name = endpoint.name || 'Unknown API';

    // ── Determine severity ──────────────────────────
    let severity = 'critical';
    if (uptime !== null && uptime >= 90) severity = 'warning';
    if (uptime !== null && uptime >= 95) severity = 'moderate';

    // ── Build diagnosis based on status code ────────
    const diagnosis = getDiagnosisForStatusCode(statusCode, responseTime, url);
    const rootCauses = getRootCauses(statusCode, responseTime, uptime, url, method);
    const recommendations = getRecommendations(statusCode, responseTime, uptime, url, method);

    return {
        severity,
        statusCode,
        responseTime,
        uptime,
        diagnosis,
        rootCauses,
        recommendations,
        analyzedAt: new Date().toLocaleString(),
    };
}

function getDiagnosisForStatusCode(statusCode, responseTime, url) {
    // Timeout / no response
    if (statusCode === null || statusCode === 0) {
        if (responseTime && responseTime > 10000) {
            return 'The API endpoint is experiencing a **connection timeout**. The server failed to respond within the expected window, which usually indicates the server is overloaded, unresponsive, or the network path has been disrupted.';
        }
        return 'The API endpoint is **completely unreachable**. No HTTP response was received, indicating either a DNS resolution failure, network connectivity issue, or the server process has crashed entirely.';
    }

    const diagnosisMap = {
        400: 'The server is rejecting requests with a **400 Bad Request** error. This typically means the request payload or parameters have become invalid — possibly due to a schema change, missing required fields, or corrupted request headers.',
        401: 'The API is returning **401 Unauthorized**. Authentication credentials (API key, token, or session) have expired, been revoked, or are no longer valid for this endpoint.',
        403: 'Access is being denied with a **403 Forbidden** response. The API key may lack the required permissions, IP restrictions may have changed, or rate-limiting/WAF rules are blocking the request.',
        404: 'The endpoint is returning **404 Not Found**. The API route may have been deprecated, the URL path changed in a recent update, or the resource being monitored no longer exists.',
        405: 'The server is returning **405 Method Not Allowed**. The HTTP method being used is not supported for this endpoint — the API may have changed its accepted methods.',
        408: 'A **408 Request Timeout** occurred. The server began processing but took too long. This often indicates backend queue congestion or database query delays.',
        429: 'The API is returning **429 Too Many Requests**. Rate limits have been exceeded. The monitoring frequency may be too aggressive, or shared quota is being consumed by other consumers.',
        500: 'The server returned a **500 Internal Server Error**. This is an unhandled exception on the API server side — typically caused by bugs in recently deployed code, misconfigured environment variables, or database connectivity issues.',
        502: 'A **502 Bad Gateway** was received. The upstream server (application server behind the load balancer/reverse proxy) is failing to respond correctly. This often occurs during deployments or when the application process crashes.',
        503: 'The API is returning **503 Service Unavailable**. The server is either in maintenance mode, overwhelmed by traffic, or the application pool has been exhausted. This is usually a temporary condition.',
        504: 'A **504 Gateway Timeout** occurred. The reverse proxy or load balancer timed out waiting for the upstream application server. This suggests severe backend latency or a completely unresponsive application layer.',
    };

    if (diagnosisMap[statusCode]) {
        return diagnosisMap[statusCode];
    }

    if (statusCode >= 500) {
        return `The server returned a **${statusCode} server error**. This indicates an issue on the API provider's infrastructure that is preventing successful request processing.`;
    }
    if (statusCode >= 400) {
        return `The API returned a **${statusCode} client error**. The request configuration may need adjustment, or the API's requirements have changed.`;
    }

    return `The endpoint returned HTTP status **${statusCode}**, which is being flagged as unsuccessful. Review the API's expected response codes to determine if this is truly an error condition.`;
}

function getRootCauses(statusCode, responseTime, uptime, url, method) {
    const causes = [];

    // Status code specific causes
    if (statusCode === null || statusCode === 0) {
        causes.push('DNS resolution failure — the domain may have expired or DNS records were modified');
        causes.push('Firewall or security group rules blocking outbound/inbound traffic on the required port');
        causes.push('The server process (e.g., nginx, node, gunicorn) has crashed and not auto-restarted');
        causes.push('SSL/TLS certificate expiration preventing secure connection establishment');
    } else if (statusCode === 401 || statusCode === 403) {
        causes.push('API key or authentication token has expired or been rotated');
        causes.push('IP address whitelist/allowlist has been updated, excluding the monitoring server');
        causes.push('Account billing issue — subscription may have lapsed, revoking API access');
        causes.push('CORS or security policy changes rejecting the request origin');
    } else if (statusCode === 404) {
        causes.push('API version deprecation — the endpoint URL path has changed (e.g., /v1→/v2)');
        causes.push('Resource or route was recently removed or renamed in a deployment');
        causes.push('Incorrect URL configuration in the monitoring setup');
    } else if (statusCode === 429) {
        causes.push('Rate limit quota exhausted — too many requests within the rate window');
        causes.push('Monitoring check interval is too frequent for this API\'s rate policy');
        causes.push('Other applications or team members consuming shared API quota');
    } else if (statusCode >= 500) {
        causes.push('Unhandled application exception in recently deployed code');
        causes.push('Database connection pool exhaustion or database server downtime');
        causes.push('Memory leak or resource exhaustion causing the application process to fail');
        causes.push('Infrastructure issue — hosting provider outage or container orchestration failure');
    }

    // Response time based causes
    if (responseTime && responseTime > 5000) {
        causes.push('Severe backend latency suggesting database query performance degradation');
        causes.push('Network congestion or routing issues between monitoring server and API host');
    }

    // Uptime based causes
    if (uptime !== null && uptime < 50) {
        causes.push('Persistent instability pattern — this may indicate a fundamental infrastructure problem requiring immediate attention');
    } else if (uptime !== null && uptime < 80) {
        causes.push('Intermittent failures pattern — possibly caused by auto-scaling issues, memory leaks, or periodic resource contention');
    }

    return causes;
}

function getRecommendations(statusCode, responseTime, uptime, url, method) {
    const recs = [];

    // Immediate actions
    if (statusCode === null || statusCode === 0) {
        recs.push({
            priority: 'high',
            title: 'Verify Server Health',
            desc: 'SSH into the server or check the hosting dashboard to confirm the application process is running. Restart if necessary and check system logs for crash reports.'
        });
        recs.push({
            priority: 'high',
            title: 'Check DNS & SSL Certificates',
            desc: 'Verify the domain resolves correctly using `nslookup` or `dig`. Check SSL certificate expiration with `openssl s_client -connect host:443`.'
        });
        recs.push({
            priority: 'medium',
            title: 'Review Firewall Rules',
            desc: 'Ensure port 443 (HTTPS) or 80 (HTTP) is open in security groups, iptables, or cloud firewall settings. Check for recent changes.'
        });
    } else if (statusCode === 401 || statusCode === 403) {
        recs.push({
            priority: 'high',
            title: 'Rotate API Credentials',
            desc: 'Generate a new API key from the provider\'s dashboard. Update the endpoint configuration with the fresh credentials immediately.'
        });
        recs.push({
            priority: 'medium',
            title: 'Verify API Permissions & Scopes',
            desc: 'Check that the API key has the required scopes/permissions for this endpoint. Some providers require explicit scope grants for specific routes.'
        });
        recs.push({
            priority: 'low',
            title: 'Set Up Key Expiry Alerts',
            desc: 'Configure proactive alerts for API key expiration dates to prevent future authentication failures before they impact monitoring.'
        });
    } else if (statusCode === 404) {
        recs.push({
            priority: 'high',
            title: 'Update Endpoint URL',
            desc: 'Check the API provider\'s documentation for the current endpoint path. Update the URL in your monitoring configuration to match the latest API version.'
        });
        recs.push({
            priority: 'medium',
            title: 'Review API Changelog',
            desc: 'Check the provider\'s changelog or release notes for any recent breaking changes, deprecations, or route modifications.'
        });
    } else if (statusCode === 429) {
        recs.push({
            priority: 'high',
            title: 'Reduce Check Frequency',
            desc: 'Increase the monitoring interval (e.g., from 1 min to 5 min) to stay within rate limits. Coordinate with other API consumers to distribute load.'
        });
        recs.push({
            priority: 'medium',
            title: 'Implement Request Caching',
            desc: 'If possible, cache responses and reduce direct API calls. Consider using conditional requests (ETag/If-Modified-Since) to minimize quota usage.'
        });
        recs.push({
            priority: 'low',
            title: 'Upgrade API Tier',
            desc: 'If higher monitoring frequency is needed, consider upgrading to a higher API plan with increased rate limits.'
        });
    } else if (statusCode >= 500) {
        recs.push({
            priority: 'high',
            title: 'Check Application Logs',
            desc: 'Review server-side error logs (stderr, application log files, or log aggregators like Datadog/CloudWatch) for stack traces and error details.'
        });
        recs.push({
            priority: 'high',
            title: 'Review Recent Deployments',
            desc: 'Check if a recent code deployment coincides with the downtime. Consider rolling back to the last known good version if the error is new.'
        });
        recs.push({
            priority: 'medium',
            title: 'Monitor Database Health',
            desc: 'Verify database connectivity, connection pool status, and query performance. Check for long-running queries or lock contention.'
        });
        recs.push({
            priority: 'medium',
            title: 'Set Up Auto-Restart Policies',
            desc: 'Configure process managers (PM2, systemd, Kubernetes liveness probes) to automatically restart failed application instances.'
        });
    }

    // Response time recommendations
    if (responseTime && responseTime > 5000) {
        recs.push({
            priority: 'medium',
            title: 'Investigate Latency Sources',
            desc: `Response time of ${responseTime}ms is critically high. Profile the API endpoint to identify slow database queries, external service calls, or CPU-intensive operations.`
        });
    }

    // Uptime-based long-term recommendations
    if (uptime !== null && uptime < 80) {
        recs.push({
            priority: 'high',
            title: 'Implement Redundancy',
            desc: 'With uptime below 80%, consider deploying the API across multiple availability zones or regions with a load balancer for automatic failover.'
        });
    }

    if (recs.length === 0) {
        recs.push({
            priority: 'medium',
            title: 'Manual Investigation Required',
            desc: 'The error pattern doesn\'t match common failure modes. Check the API provider\'s status page, review recent changes, and contact their support team if the issue persists.'
        });
    }

    return recs;
}

// ── Modal / UI Controller ──────────────────────────────────────

/** Cached endpoint data for re-run */
let _aiCurrentEndpoint = null;

/**
 * Open the AI Analyzer modal for a given endpoint.
 * Called from table rows and monitor cards.
 */
window.openAIAnalyzer = async function (endpointId) {
    // Show modal immediately with loading state
    const overlay = document.getElementById('ai-analyzer-overlay');
    if (!overlay) return;

    overlay.classList.add('active');
    showAILoading();

    try {
        // Fetch latest endpoint data with logs
        const data = await apiRequest(`/api/endpoints/${endpointId}`);
        const ep = data.endpoint;

        // Also fetch recent logs for richer context
        let logs = [];
        try {
            const logData = await apiRequest(`/api/endpoints/${endpointId}/logs?range=1d&limit=20`);
            logs = logData.logs || [];
        } catch (e) { /* logs are optional enrichment */ }

        // Merge latest log data into endpoint if not already present
        if (logs.length > 0 && !ep.last_status_code) {
            const latestLog = logs[0];
            ep.last_status_code = latestLog.status_code;
            ep.last_response_time = latestLog.response_time;
            ep.is_down = !latestLog.is_success;
        }

        // Calculate failure rate from logs
        if (logs.length > 0) {
            const failures = logs.filter(l => !l.is_success).length;
            ep._failureRate = Math.round((failures / logs.length) * 100);
            ep._recentLogs = logs;
        }

        _aiCurrentEndpoint = ep;

        // Simulate analysis delay for UX polish
        await new Promise(r => setTimeout(r, 1800));

        const analysis = generateAIAnalysis(ep);
        renderAIAnalysis(ep, analysis);
    } catch (err) {
        renderAIError(err.message || 'Failed to analyze this endpoint.');
    }
};

function showAILoading() {
    const body = document.getElementById('ai-modal-body');
    const footer = document.getElementById('ai-modal-footer');
    const subtitle = document.getElementById('ai-modal-subtitle');

    if (subtitle) subtitle.textContent = 'Analyzing endpoint...';
    if (footer) footer.style.display = 'none';

    body.innerHTML = `
        <div class="ai-loading">
            <div class="ai-loading-orb">
                <i class="fa-solid fa-microchip"></i>
            </div>
            <div class="ai-loading-text">
                Analyzing downtime patterns
                <span class="ai-loading-dots">
                    <span></span><span></span><span></span>
                </span>
            </div>
        </div>
    `;
}

function renderAIAnalysis(ep, analysis) {
    const body = document.getElementById('ai-modal-body');
    const footer = document.getElementById('ai-modal-footer');
    const subtitle = document.getElementById('ai-modal-subtitle');

    if (subtitle) subtitle.textContent = `${escapeHtml(ep.name)} — ${escapeHtml(ep.url)}`;
    if (footer) footer.style.display = 'flex';

    // Status bar values
    const statusCodeDisplay = analysis.statusCode ? `${analysis.statusCode}` : 'N/A';
    const statusCodeClass = analysis.statusCode
        ? (analysis.statusCode >= 500 ? 'danger' : analysis.statusCode >= 400 ? 'warning' : 'info')
        : 'muted';

    const rtDisplay = analysis.responseTime ? `${analysis.responseTime}ms` : 'Timeout';
    const rtClass = !analysis.responseTime ? 'danger' : (analysis.responseTime > 3000 ? 'warning' : 'info');

    const uptimeDisplay = analysis.uptime !== null ? `${analysis.uptime}%` : 'N/A';
    const uptimeClass = analysis.uptime === null ? 'muted'
        : analysis.uptime >= 95 ? 'success'
        : analysis.uptime >= 80 ? 'warning'
        : 'danger';

    // Root causes HTML
    const causesHtml = analysis.rootCauses.map((cause, i) => `
        <div class="ai-cause-item">
            <span class="ai-cause-num">${i + 1}</span>
            <span class="ai-cause-text">${escapeHtml(cause)}</span>
        </div>
    `).join('');

    // Recommendations HTML
    const recsHtml = analysis.recommendations.map(rec => `
        <div class="ai-rec-card">
            <span class="ai-rec-priority ${rec.priority}">${rec.priority}</span>
            <div class="ai-rec-content">
                <div class="ai-rec-title">${escapeHtml(rec.title)}</div>
                <div class="ai-rec-desc">${escapeHtml(rec.desc)}</div>
            </div>
        </div>
    `).join('');

    // Render the formatted diagnosis (convert **bold** markdown to <strong>)
    const diagnosisFormatted = analysis.diagnosis
        .replace(/\*\*(.*?)\*\*/g, '<strong style="color:#EF4444;">$1</strong>');

    body.innerHTML = `
        <!-- Status Summary Bar -->
        <div class="ai-status-bar">
            <div class="ai-status-item">
                <div class="ai-status-value ${statusCodeClass}">${statusCodeDisplay}</div>
                <div class="ai-status-label">Status Code</div>
            </div>
            <div class="ai-status-item">
                <div class="ai-status-value ${rtClass}">${rtDisplay}</div>
                <div class="ai-status-label">Response Time</div>
            </div>
            <div class="ai-status-item">
                <div class="ai-status-value ${uptimeClass}">${uptimeDisplay}</div>
                <div class="ai-status-label">Uptime (24h)</div>
            </div>
        </div>

        <!-- Section 1: Diagnosis -->
        <div class="ai-section">
            <div class="ai-section-header">
                <div class="ai-section-icon danger">
                    <i class="fa-solid fa-stethoscope"></i>
                </div>
                <span class="ai-section-title">Diagnosis</span>
            </div>
            <div class="ai-diagnosis-card">
                <div class="ai-diagnosis-label">Detected Issue</div>
                <div class="ai-diagnosis-text">${diagnosisFormatted}</div>
            </div>
        </div>

        <!-- Section 2: Root Causes -->
        <div class="ai-section">
            <div class="ai-section-header">
                <div class="ai-section-icon warning">
                    <i class="fa-solid fa-magnifying-glass-chart"></i>
                </div>
                <span class="ai-section-title">Probable Root Causes</span>
            </div>
            <div class="ai-causes-list">
                ${causesHtml}
            </div>
        </div>

        <!-- Section 3: Recommendations -->
        <div class="ai-section">
            <div class="ai-section-header">
                <div class="ai-section-icon success">
                    <i class="fa-solid fa-lightbulb"></i>
                </div>
                <span class="ai-section-title">Recommended Action Plan</span>
            </div>
            <div class="ai-recommendations">
                ${recsHtml}
            </div>
        </div>

        <!-- Section 4: Summary -->
        <div class="ai-section">
            <div class="ai-section-header">
                <div class="ai-section-icon info">
                    <i class="fa-solid fa-clock-rotate-left"></i>
                </div>
                <span class="ai-section-title">Analysis Metadata</span>
            </div>
            <div style="font-size:0.78rem; color:var(--text-muted); padding: 0.5rem 0;">
                <span style="margin-right: 1.5rem;"><i class="fa-solid fa-calendar-day" style="margin-right:4px; color:#06B6D4;"></i> Analyzed: ${analysis.analyzedAt}</span>
                <span><i class="fa-solid fa-server" style="margin-right:4px; color:#06B6D4;"></i> Endpoint: ${escapeHtml(ep.method || 'GET')} ${escapeHtml(ep.url)}</span>
            </div>
        </div>
    `;
}

function renderAIError(message) {
    const body = document.getElementById('ai-modal-body');
    const footer = document.getElementById('ai-modal-footer');
    if (footer) footer.style.display = 'none';

    body.innerHTML = `
        <div class="ai-loading" style="color: var(--danger-color);">
            <div class="ai-loading-orb" style="border-color: rgba(239,68,68,0.3); background: rgba(239,68,68,0.1);">
                <i class="fa-solid fa-triangle-exclamation" style="color:#EF4444; animation:none;"></i>
            </div>
            <div class="ai-loading-text" style="color: #EF4444;">
                Analysis Failed
            </div>
            <div style="font-size: 0.82rem; color: var(--text-muted); max-width: 320px; text-align: center; line-height: 1.6;">
                ${escapeHtml(message)}
            </div>
        </div>
    `;
}

function closeAIAnalyzer() {
    const overlay = document.getElementById('ai-analyzer-overlay');
    if (overlay) overlay.classList.remove('active');
}

function rerunAIAnalysis() {
    if (_aiCurrentEndpoint) {
        showAILoading();
        setTimeout(() => {
            const analysis = generateAIAnalysis(_aiCurrentEndpoint);
            renderAIAnalysis(_aiCurrentEndpoint, analysis);
        }, 1500);
    }
}

// ── Initialize modal DOM on page load ──────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    // Only inject the modal if it doesn't exist yet
    if (document.getElementById('ai-analyzer-overlay')) return;

    const modal = document.createElement('div');
    modal.id = 'ai-analyzer-overlay';
    modal.className = 'ai-modal-overlay';
    modal.innerHTML = `
        <div class="ai-modal">
            <div class="ai-modal-header">
                <div class="ai-modal-icon">
                    <i class="fa-solid fa-brain"></i>
                </div>
                <div class="ai-modal-title-group">
                    <div class="ai-modal-title">
                        AI Downtime Analyzer
                        <span class="ai-badge"><i class="fa-solid fa-sparkles" style="font-size:0.55rem;"></i> AI</span>
                    </div>
                    <div class="ai-modal-subtitle" id="ai-modal-subtitle">Analyzing endpoint...</div>
                </div>
                <button class="ai-modal-close" onclick="closeAIAnalyzer()" title="Close">
                    <i class="fa-solid fa-xmark"></i>
                </button>
            </div>
            <div class="ai-modal-body" id="ai-modal-body">
                <!-- Content injected dynamically -->
            </div>
            <div class="ai-modal-footer" id="ai-modal-footer" style="display:none;">
                <div class="ai-footer-hint">
                    <i class="fa-solid fa-robot"></i>
                    <span>AI analysis based on real-time monitoring data</span>
                </div>
                <button class="btn-ai-rerun" onclick="rerunAIAnalysis()">
                    <i class="fa-solid fa-rotate-right"></i>
                    Re-analyze
                </button>
            </div>
        </div>
    `;
    document.body.appendChild(modal);

    // Close on overlay click
    modal.addEventListener('click', (e) => {
        if (e.target === modal) closeAIAnalyzer();
    });

    // Close on Escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') closeAIAnalyzer();
    });
});
