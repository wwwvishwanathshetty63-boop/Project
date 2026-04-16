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
                // You would normally fetch new data here
                showNotification('Data refreshed successfully');
            }, 1000);
        });
    }

    // Mock notification function
    window.showNotification = function (message) {
        // Simple mock for now
        console.log("Notification:", message);
    };
});
