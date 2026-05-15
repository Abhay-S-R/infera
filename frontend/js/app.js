// frontend/js/app.js

class App {
    constructor() {
        this.init();
    }

    init() {
        // Initialize routing
        window.addEventListener('hashchange', () => this.handleRouting());
        this.handleRouting();
        
        // Initialize components
        if (typeof initWebSocket === 'function') {
            initWebSocket();
        }
        
        if (typeof initPipeline === 'function') {
            initPipeline();
        }

        this.setupSidebarNavigation();
    }

    handleRouting() {
        const hash = window.location.hash || '#dashboard';
        const pageName = hash.substring(1);
        
        // Basic routing logic: Update title and active state in sidebar
        const titleElement = document.querySelector('.page-title');
        if (titleElement) {
            titleElement.textContent = pageName.charAt(0).toUpperCase() + pageName.slice(1);
        }

        // Update active class on nav items based on hash
        const navItems = document.querySelectorAll('.nav-item');
        navItems.forEach(item => {
            const text = item.textContent.trim().toLowerCase();
            if (text === pageName) {
                item.classList.add('active');
            } else {
                item.classList.remove('active');
            }
        });
    }

    setupSidebarNavigation() {
        const navItems = document.querySelectorAll('.nav-item');
        navItems.forEach(item => {
            item.addEventListener('click', (e) => {
                const text = e.currentTarget.textContent.trim().toLowerCase();
                window.location.hash = `#${text}`;
            });
        });
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.app = new App();
});
