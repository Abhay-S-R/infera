// frontend/js/competitors.js

class CompetitorManager {
    constructor() {
        this.container = document.getElementById('competitor-config');
        this.listEl = null;
        this.inputEl = null;
    }

    init() {
        if (!this.container) return;
        this.render();
        this.fetchCompetitors();
    }

    render() {
        this.container.innerHTML = `
            <div class="card-header" style="margin-bottom: 1rem;">
                Tracked Competitors
                <div class="card-icon">
                    <i class="ph ph-binoculars"></i>
                </div>
            </div>
            <div class="competitor-add" style="display: flex; gap: 0.5rem; margin-bottom: 1rem;">
                <input type="text" id="competitor-add-input" placeholder="Competitor name..." class="form-input" style="flex: 1;">
                <button id="competitor-add-btn" class="btn-primary">
                    <i class="ph ph-plus"></i> Add
                </button>
            </div>
            <div id="competitor-list" class="competitor-list"></div>
        `;

        this.listEl = document.getElementById('competitor-list');
        this.inputEl = document.getElementById('competitor-add-input');

        document.getElementById('competitor-add-btn').addEventListener('click', () => this.addCompetitor());
        this.inputEl.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                this.addCompetitor();
            }
        });
    }

    async fetchCompetitors() {
        try {
            const response = await fetch('http://localhost:8000/api/competitors');
            if (!response.ok) throw new Error('Failed to fetch');
            const data = await response.json();
            const competitors = Array.isArray(data) ? data : (data.competitors || []);
            this.renderList(competitors);
        } catch (e) {
            this.listEl.innerHTML = '<div style="color: var(--text-muted); font-size: 0.8rem; text-align: center; padding: 1rem;">No competitors tracked yet</div>';
        }
    }

    renderList(competitors) {
        if (!competitors || competitors.length === 0) {
            this.listEl.innerHTML = '<div style="color: var(--text-muted); font-size: 0.8rem; text-align: center; padding: 1rem;">No competitors tracked yet</div>';
            return;
        }

        this.listEl.innerHTML = competitors.map(c => {
            const name = typeof c === 'string' ? c : (c.name || c.competitor || c);
            const id = typeof c === 'string' ? c : (c.id || c.name || c);
            return `
                <div class="competitor-item">
                    <div class="competitor-info">
                        <span class="status-indicator status-success"></span>
                        <span class="competitor-name">${name}</span>
                    </div>
                    <button class="competitor-remove" data-id="${id}" title="Remove">
                        <i class="ph ph-x"></i>
                    </button>
                </div>
            `;
        }).join('');

        this.listEl.querySelectorAll('.competitor-remove').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const id = e.currentTarget.dataset.id;
                this.removeCompetitor(id);
            });
        });
    }

    async addCompetitor() {
        const name = this.inputEl.value.trim();
        if (!name) return;

        try {
            const response = await fetch('http://localhost:8000/api/competitors', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: name })
            });
            if (!response.ok) throw new Error('Failed to add');
            this.inputEl.value = '';
            this.fetchCompetitors();
        } catch (e) {
            console.error('Error adding competitor:', e);
        }
    }

    async removeCompetitor(id) {
        try {
            const response = await fetch(`http://localhost:8000/api/competitors/${encodeURIComponent(id)}`, {
                method: 'DELETE'
            });
            if (!response.ok) throw new Error('Failed to remove');
            this.fetchCompetitors();
        } catch (e) {
            console.error('Error removing competitor:', e);
        }
    }
}

function initCompetitors() {
    window.competitorManager = new CompetitorManager();
    window.competitorManager.init();
}
