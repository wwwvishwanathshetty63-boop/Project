// ── SYNAPSE GLOBAL INTERACTIONS ──

document.addEventListener('DOMContentLoaded', () => {
    const isLanding = document.body.dataset.page === 'landing';

    if (isLanding) {
        initCursor();       // Custom cursor: landing page only
        initScrollAnimations();
        initPillNav();
    }

    populateSidebarUser();
});

// ── CURSOR ANIMATION (landing page only) ──
function initCursor() {
    if (!window.matchMedia('(pointer: fine)').matches) return;

    // Hide system cursor on the landing page
    document.body.style.cursor = 'none';

    // Restore pointer on interactive elements so clicks always fire
    const cursorStyle = document.createElement('style');
    cursorStyle.id = 'synapse-cursor-style';
    cursorStyle.textContent = 'a,button,input,select,textarea,label,[role="button"],.nav-item,.menu-item,.filter-pill,.btn-shiny,.btn-secondary,.btn-glass,.topbar-action,.icon-btn,.action-btn,.modal-close{cursor:pointer!important}';
    document.head.appendChild(cursorStyle);

    // Create cursor elements if they don't exist
    if (!document.getElementById('cursor-dot')) {
        const spotlight = document.createElement('div'); spotlight.id = 'cursor-spotlight';
        const ring = document.createElement('div'); ring.id = 'cursor-ring';
        const dot = document.createElement('div'); dot.id = 'cursor-dot';
        document.body.appendChild(spotlight);
        document.body.appendChild(ring);
        document.body.appendChild(dot);
    }

    const spotlight = document.getElementById('cursor-spotlight');
    const dot = document.getElementById('cursor-dot');
    const ring = document.getElementById('cursor-ring');

    let mouseX = 0, mouseY = 0;
    let ringX = 0, ringY = 0;
    let isVisible = false;

    // Interactive selectors for cursor style change (purely cosmetic)
    const interactiveSelectors = 'a, button, .glass-card, .btn-shiny, .nav-item, .menu-item, input, select, textarea, label';

    function showCursor() {
        if (!isVisible) {
            dot.style.opacity = '1';
            ring.style.opacity = '1';
            spotlight.style.opacity = '1';
            isVisible = true;
        }
    }

    document.addEventListener('mousemove', (e) => {
        mouseX = e.clientX;
        mouseY = e.clientY;
        showCursor();

        dot.style.left = mouseX + 'px';
        dot.style.top = mouseY + 'px';
        spotlight.style.left = mouseX + 'px';
        spotlight.style.top = mouseY + 'px';
    }, { passive: true });

    function animateRing() {
        ringX += (mouseX - ringX) * 0.12;
        ringY += (mouseY - ringY) * 0.12;
        ring.style.left = ringX + 'px';
        ring.style.top = ringY + 'px';
        requestAnimationFrame(animateRing);
    }
    animateRing();

    document.addEventListener('mouseover', (e) => {
        if (e.target.closest(interactiveSelectors)) {
            dot.style.width = '14px';
            dot.style.height = '14px';
            dot.style.background = '#22d3ee';
            dot.style.boxShadow = '0 0 16px rgba(34,211,238,0.9), 0 0 6px rgba(34,211,238,1)';
            ring.style.width = '56px';
            ring.style.height = '56px';
            ring.style.borderColor = 'rgba(34,211,238,0.5)';
            spotlight.style.background = 'radial-gradient(circle, rgba(6,182,212,0.1) 0%, rgba(139,92,246,0.05) 30%, transparent 70%)';
        }
    });

    document.addEventListener('mouseout', (e) => {
        if (e.target.closest(interactiveSelectors)) {
            dot.style.width = '8px';
            dot.style.height = '8px';
            dot.style.background = '#a78bfa';
            dot.style.boxShadow = '0 0 12px rgba(167,139,250,0.8), 0 0 4px rgba(167,139,250,1)';
            ring.style.width = '36px';
            ring.style.height = '36px';
            ring.style.borderColor = 'rgba(139,92,246,0.4)';
            spotlight.style.background = 'radial-gradient(circle, rgba(139,92,246,0.07) 0%, rgba(6,182,212,0.04) 30%, transparent 70%)';
        }
    });

    document.addEventListener('mousedown', () => {
        dot.style.transform = 'translate(-50%, -50%) scale(0.7)';
        ring.style.transform = 'translate(-50%, -50%) scale(0.85)';
    });
    document.addEventListener('mouseup', () => {
        dot.style.transform = 'translate(-50%, -50%) scale(1)';
        ring.style.transform = 'translate(-50%, -50%) scale(1)';
    });

    document.addEventListener('mouseleave', () => {
        dot.style.opacity = '0';
        ring.style.opacity = '0';
        spotlight.style.opacity = '0';
        isVisible = false;
    });
}

// ── SCROLL ANIMATIONS (landing page only) ──
function initScrollAnimations() {
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('in-view');
                observer.unobserve(entry.target); // Stop observing once visible
            }
        });
    }, { threshold: 0.05 });

    // Only animate elements that are NOT already in the viewport
    document.querySelectorAll('.glass-card, section, .hero-content').forEach(el => {
        const rect = el.getBoundingClientRect();
        // Skip elements already visible on load
        if (rect.top > window.innerHeight * 0.95) {
            el.style.opacity = '0';
            el.style.transform = 'translateY(24px)';
            el.style.transition = 'opacity 0.8s ease, transform 0.8s cubic-bezier(0.23, 1, 0.32, 1)';
            observer.observe(el);
        }
    });

    // Add a helper class for the CSS
    const style = document.createElement('style');
    style.innerHTML = '.in-view { opacity: 1 !important; transform: translateY(0) !important; }';
    document.head.appendChild(style);
}

// ── PILL NAV BEHAVIOR ──
function initPillNav() {
    const nav = document.querySelector('.navbar');
    if (!nav) return;

    window.addEventListener('scroll', () => {
        const inner = document.querySelector('.nav-inner');
        if (!inner) return;
        if (window.scrollY > 50) {
            nav.style.top = '1rem';
            inner.style.background = 'rgba(5,5,5,0.9)';
        } else {
            nav.style.top = '1.5rem';
            inner.style.background = 'rgba(10,10,10,0.75)';
        }
    });
}

// ── SIDEBAR USER POPULATION ──
// Handles both old (.sidebar-footer) and new (.sidebar-user) class names
function populateSidebarUser() {
    try {
        const auth = localStorage.getItem('auth_user');
        if (!auth) return;
        const user = JSON.parse(auth);
        if (!user) return;

        const initials = (user.name || user.email || 'U')
            .split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase();
        const displayName = user.name || user.email || 'User';
        const role = user.role || 'Agent';

        // Avatar
        document.querySelectorAll('.sidebar-user .user-avatar-small, .sidebar-footer .user-avatar-small').forEach(el => {
            el.textContent = initials;
        });
        // Name
        document.querySelectorAll('.sidebar-user .user-name, .sidebar-footer .user-name').forEach(el => {
            el.textContent = displayName;
        });
        // Role
        document.querySelectorAll('.sidebar-user .user-role, .sidebar-footer .user-role').forEach(el => {
            el.textContent = role;
        });
        // Topbar avatar
        document.querySelectorAll('.topbar-right .user-avatar-small, .top-bar-right .user-avatar-small').forEach(el => {
            el.textContent = initials;
        });
    } catch (e) { /* Ignore parse errors */ }
}
