// frontend/js/app.js

class App {
    constructor() {
        this.init();
    }

    init() {
        window.addEventListener('hashchange', () => this.handleRouting());
        this.handleRouting();
        
        if (typeof initWebSocket === 'function') {
            initWebSocket();
        }
        
        if (typeof initPipeline === 'function') {
            initPipeline();
        }

        if (typeof initReports === 'function') {
            initReports();
        }

        this.setupSidebarNavigation();
        this.setupManualTriggerForm();
    }

    handleRouting() {
        const hash = window.location.hash || '#dashboard';
        const pageName = hash.substring(1);
        
        const titleElement = document.querySelector('.page-title');
        if (titleElement) {
            titleElement.textContent = pageName.charAt(0).toUpperCase() + pageName.slice(1);
        }

        const navItems = document.querySelectorAll('.nav-item');
        navItems.forEach(item => {
            const text = item.textContent.trim().toLowerCase();
            if (text === pageName) {
                item.classList.add('active');
            } else {
                item.classList.remove('active');
            }
        });
        
        // Toggle page sections
        const pages = document.querySelectorAll('.page-section');
        pages.forEach(page => {
            if (page.id === `page-${pageName}`) {
                page.style.display = 'block';
                // If it's reports, fetch again just in case
                if (pageName === 'reports' && window.reportsManager) {
                    window.reportsManager.fetchReports();
                    window.reportsManager.backToList();
                }
            } else {
                page.style.display = 'none';
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

    setupManualTriggerForm() {
        const form = document.getElementById('analyze-form');
        if (!form) return;
        
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const competitorName = document.getElementById('competitor-name').value;
            const question = document.getElementById('analyze-question').value;
            const submitBtn = form.querySelector('button[type="submit"]');
            
            const originalText = submitBtn.innerHTML;
            submitBtn.innerHTML = '<i class="ph ph-spinner ph-spin"></i> Launching...';
            submitBtn.disabled = true;
            
            try {
                // Post to API
                const response = await fetch('http://localhost:8000/api/analyze', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        competitor: competitorName,
                        question: question
                    })
                });
                
                if (!response.ok) throw new Error('Failed to start analysis');
                
                // Add a local activity event
                if (window.addActivityEvent) {
                    window.addActivityEvent({
                        agent: 'System',
                        status: 'success',
                        message: `Started analysis for ${competitorName}: "${question}"`
                    });
                }
                
                form.reset();
            } catch (err) {
                console.error(err);
                alert('Error starting analysis: ' + err.message);
            } finally {
                submitBtn.innerHTML = originalText;
                submitBtn.disabled = false;
            }
        });
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.app = new App();
});
