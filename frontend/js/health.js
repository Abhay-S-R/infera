// frontend/js/health.js

class HealthPanel {
    constructor() {
        this.container = document.getElementById('health-panel');
        this.pollInterval = null;
    }

    start() {
        if (!this.container) return;
        this.fetchStats();
        this.pollInterval = setInterval(() => this.fetchStats(), 10000);
    }

    stop() {
        if (this.pollInterval) {
            clearInterval(this.pollInterval);
            this.pollInterval = null;
        }
    }

    async fetchStats() {
        try {
            const response = await fetch('http://127.0.0.1:8000/api/health/stats');
            if (!response.ok) throw new Error('Health endpoint unavailable');
            const stats = await response.json();
            this.render(stats);
        } catch (e) {
            this.renderOffline();
        }
    }

    render(stats) {
        const activeWorkflows = stats.active_workflows ?? 0;
        const totalReports = stats.total_reports ?? 0;
        const recentCompletions = stats.recent_completions ?? [];

        this.container.innerHTML = `
            <div class="card-header" style="margin-bottom: 1rem;">
                System Health
                <div class="card-icon" style="background: rgba(52, 211, 153, 0.08); color: #34d399;">
                    <i class="ph ph-heartbeat"></i>
                </div>
            </div>
            <div class="health-stats">
                <div class="health-stat">
                    <span class="health-stat-value">${activeWorkflows}</span>
                    <span class="health-stat-label">Active Workflows</span>
                </div>
                <div class="health-stat">
                    <span class="health-stat-value">${totalReports}</span>
                    <span class="health-stat-label">Total Reports</span>
                </div>
            </div>
            <div class="health-completions">
                <div class="health-completions-title">Recent Completions</div>
                ${recentCompletions.length === 0
                    ? '<div class="health-empty">No recent completions</div>'
                    : recentCompletions.slice(0, 5).map(c => `
                        <div class="health-completion-item">
                            <span class="status-indicator status-success"></span>
                            <span class="health-completion-name">${c.competitor || c.title || 'Analysis'}</span>
                            <span class="health-completion-time">${c.completed_at ? new Date(c.completed_at).toLocaleTimeString() : ''}</span>
                        </div>
                    `).join('')}
            </div>
        `;
    }

    renderOffline() {
        this.container.innerHTML = `
            <div class="card-header" style="margin-bottom: 1rem;">
                System Health
                <div class="card-icon" style="background: rgba(248, 113, 113, 0.08); color: #f87171;">
                    <i class="ph ph-heartbeat"></i>
                </div>
            </div>
            <div style="text-align: center; padding: 1.5rem 0;">
                <div style="color: var(--text-muted); font-size: 0.8rem;">Unable to reach backend</div>
                <div style="color: var(--text-muted); font-size: 0.68rem; margin-top: 0.3rem;">Retrying every 10s...</div>
            </div>
        `;
    }
}

function initHealth() {
    window.healthPanel = new HealthPanel();
    window.healthPanel.start();
}
