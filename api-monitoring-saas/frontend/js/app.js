/**
 * API Monitor SaaS — Core Application Module
 * Handles authentication, API calls, and UI utilities.
 */

// Auto-detect API base: works both via Flask (localhost:5000) and opened directly (file://)
const API_BASE = (window.location.protocol === 'file:' || window.location.origin === 'null')
    ? 'http://localhost:5000'
    : window.location.origin;

// ---- State ----
const AppState = {
    token: localStorage.getItem('auth_token') || null,
    user: JSON.parse(localStorage.getItem('auth_user') || 'null'),
};

// ---- API Client ----
async function apiRequest(endpoint, options = {}) {
    const url = `${API_BASE}${endpoint}`;
    const headers = {
        'Content-Type': 'application/json',
        ...(options.headers || {}),
    };

    if (AppState.token) {
        headers['Authorization'] = `Bearer ${AppState.token}`;
    }

    try {
        const response = await fetch(url, {
            ...options,
            headers,
            body: options.body ? JSON.stringify(options.body) : undefined,
        });

        // Handle 401 immediately — redirect to login for any auth failure
        if (response.status === 401) {
            logout();
            throw new Error('Session expired. Please log in again.');
        }

        // Check if the response is JSON before parsing
        const contentType = response.headers.get('content-type') || '';
        let data;

        if (contentType.includes('application/json')) {
            data = await response.json();
        } else {
            const text = await response.text();
            if (!response.ok) {
                throw new Error(`Server error (${response.status}). Please ensure the backend is running.`);
            }
            // Try parsing as JSON anyway
            try {
                data = JSON.parse(text);
            } catch {
                throw new Error(`Unexpected server response (${response.status})`);
            }
        }

        if (!response.ok) {
            const err = new Error(data.error || `HTTP ${response.status}`);
            Object.assign(err, data);
            throw err;
        }

        return data;
    } catch (error) {
        // Tag network-level failures for callers to distinguish
        if (error instanceof TypeError && error.message === 'Failed to fetch') {
            const netError = new Error('Cannot reach server. Please check your connection.');
            netError.isNetworkError = true;
            throw netError;
        }
        throw error;
    }
}

// ---- Auth Functions ----
function saveAuth(token, user) {
    AppState.token = token;
    AppState.user = user;
    localStorage.setItem('auth_token', token);
    localStorage.setItem('auth_user', JSON.stringify(user));
}

function logout() {
    AppState.token = null;
    AppState.user = null;
    localStorage.removeItem('auth_token');
    localStorage.removeItem('auth_user');
    window.location.href = 'index.html';
}

function isAuthenticated() {
    return !!AppState.token;
}

function getUser() {
    return AppState.user;
}

// ---- Toast Notifications ----
function showToast(message, type = 'success', duration = 4000) {
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'toast-container';
        document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;

    const icons = { success: '✓', error: '✕', warning: '⚠' };
    toast.innerHTML = `<span>${icons[type] || ''}</span><span>${message}</span>`;

    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(40px)';
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

// ---- Auth Form Handling ----
function initAuthPage() {
    if (isAuthenticated()) {
        window.location.href = 'dashboard.html';
        return;
    }

    // Role tabs: Company vs Employee
    const companyTab = document.getElementById('company-tab');
    const employeeTab = document.getElementById('employee-tab');
    const companySection = document.getElementById('company-section');
    const employeeSection = document.getElementById('employee-section');
    const authTitle = document.getElementById('auth-title');
    const authSubtitle = document.getElementById('auth-subtitle');

    // Company sub-tabs (Sign In / Sign Up)
    const loginTab = document.getElementById('login-tab');
    const registerTab = document.getElementById('register-tab');
    const loginForm = document.getElementById('login-form');
    const registerForm = document.getElementById('register-form');

    // Employee login form
    const employeeLoginForm = document.getElementById('employee-login-form');

    if (!companyTab) return;

    // ---- Role tab switching ----
    companyTab.addEventListener('click', () => {
        companyTab.classList.add('active');
        employeeTab.classList.remove('active');
        companySection.style.display = 'block';
        employeeSection.style.display = 'none';
        authTitle.textContent = 'Welcome back';
        authSubtitle.textContent = 'Sign in to your company dashboard';
    });

    employeeTab.addEventListener('click', () => {
        employeeTab.classList.add('active');
        companyTab.classList.remove('active');
        employeeSection.style.display = 'block';
        companySection.style.display = 'none';
        authTitle.textContent = 'Employee Login';
        authSubtitle.textContent = 'Sign in with your Employee ID & password';
    });

    // ---- Company sub-tab switching ----
    loginTab.addEventListener('click', () => {
        loginTab.classList.add('active');
        registerTab.classList.remove('active');
        loginForm.style.display = 'block';
        registerForm.style.display = 'none';
    });

    registerTab.addEventListener('click', () => {
        registerTab.classList.add('active');
        loginTab.classList.remove('active');
        registerForm.style.display = 'block';
        loginForm.style.display = 'none';
    });

    // ---- Company Login ----
    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const btn = loginForm.querySelector('button[type="submit"]');
        btn.disabled = true;
        btn.innerHTML = '<div class="spinner"></div> Signing in...';

        try {
            const data = await apiRequest('/api/auth/login', {
                method: 'POST',
                body: {
                    email: document.getElementById('login-email').value,
                    password: document.getElementById('login-password').value,
                },
            });

            saveAuth(data.token, data.user);
            showToast('Login successful! Redirecting...');
            setTimeout(() => window.location.href = 'dashboard.html', 800);
        } catch (error) {
            showToast(error.message, 'error');
        } finally {
            btn.disabled = false;
            btn.innerHTML = 'Sign In';
        }
    });

    // ---- Company Register ----
    registerForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const btn = registerForm.querySelector('button[type="submit"]');
        btn.disabled = true;
        btn.innerHTML = '<div class="spinner"></div> Creating account...';

        try {
            const data = await apiRequest('/api/auth/register', {
                method: 'POST',
                body: {
                    name: document.getElementById('register-name').value,
                    email: document.getElementById('register-email').value,
                    password: document.getElementById('register-password').value,
                },
            });

            saveAuth(data.token, data.user);
            showToast('Company account created! Redirecting...');
            setTimeout(() => window.location.href = 'dashboard.html', 800);
        } catch (error) {
            showToast(error.message, 'error');
        } finally {
            btn.disabled = false;
            btn.innerHTML = 'Create Company Account';
        }
    });

    // ---- Employee Login ----
    employeeLoginForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const btn = employeeLoginForm.querySelector('button[type="submit"]');
        btn.disabled = true;
        btn.innerHTML = '<div class="spinner"></div> Signing in...';

        try {
            const data = await apiRequest('/api/auth/login', {
                method: 'POST',
                body: {
                    employee_id: document.getElementById('emp-id').value,
                    password: document.getElementById('emp-password').value,
                },
            });

            saveAuth(data.token, data.user);
            showToast('Login successful! Redirecting...');
            setTimeout(() => window.location.href = 'dashboard.html', 800);
        } catch (error) {
            showToast(error.message, 'error');
        } finally {
            btn.disabled = false;
            btn.innerHTML = 'Employee Sign In';
        }
    });
}

// ---- Password Visibility Toggle ----
function togglePasswordVisibility(inputId, btn) {
    const input = document.getElementById(inputId);
    if (!input) return;
    if (input.type === 'password') {
        input.type = 'text';
        btn.textContent = '🙈';
        btn.title = 'Hide password';
    } else {
        input.type = 'password';
        btn.textContent = '👁️';
        btn.title = 'Show password';
    }
}

// Auto-init on index page
document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('login-form')) {
        initAuthPage();
    }
});

// ---- Utility Functions ----
async function fetchWithRetry(endpoint, maxRetries = 3) {
    for (let attempt = 1; attempt <= maxRetries; attempt++) {
        try {
            return await apiRequest(endpoint);
        } catch (error) {
            if (error.message.includes('Session expired')) throw error;
            if (attempt === maxRetries) throw error;
            if (error.isNetworkError || error.message.includes('Server error') || error.message.includes('500')) {
                const delay = Math.min(1000 * Math.pow(2, attempt - 1), 5000);
                await new Promise(resolve => setTimeout(resolve, delay));
                continue;
            }
            throw error;
        }
    }
}

function escapeHtml(text) {
    if (text === null || text === undefined) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
