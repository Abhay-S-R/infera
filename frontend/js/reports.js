// frontend/js/reports.js

class ReportsManager {
    constructor() {
        this.container = document.getElementById('page-reports');
        this.detailContainer = document.getElementById('report-detail');
        this.listContainer = document.getElementById('reports-list');
    }

    getConfidenceBadge(confidence) {
        if (confidence === undefined || confidence === null) return '';
        const val = typeof confidence === 'string' ? parseFloat(confidence) : confidence;
        // Normalize: if value > 1, treat as percentage (e.g. 85 → 0.85)
        const norm = val > 1 ? val / 100 : val;

        let color, bg, label;
        if (norm >= 0.8) {
            color = '#34d399'; bg = 'rgba(52, 211, 153, 0.1)'; label = 'HIGH';
        } else if (norm >= 0.5) {
            color = '#fbbf24'; bg = 'rgba(251, 191, 36, 0.1)'; label = 'MED';
        } else {
            color = '#f87171'; bg = 'rgba(248, 113, 113, 0.1)'; label = 'LOW';
        }

        const displayVal = val > 1 ? Math.round(val) + '%' : Math.round(val * 100) + '%';
        return `<span class="badge" style="background: ${bg}; color: ${color}; margin-left: 0.5rem;">${displayVal} ${label}</span>`;
    }

    async fetchReports() {
        if (!this.listContainer) return;
        
        try {
            this.listContainer.innerHTML = '<div class="loading" style="color: var(--text-muted); padding: 2rem; text-align: center;">Loading reports...</div>';
            
            const response = await fetch('http://localhost:8000/api/reports');
            if (!response.ok) throw new Error('Failed to fetch reports');
            
            const reports = await response.json();
            this.renderReportsList(reports);
        } catch (e) {
            console.error(e);
            this.listContainer.innerHTML = `<div class="error" style="color: #ef4444; padding: 2rem; text-align: center;">Error loading reports: ${e.message}</div>`;
        }
    }

    renderReportsList(reports) {
        if (!reports || reports.length === 0) {
            this.listContainer.innerHTML = '<div class="empty-state" style="color: var(--text-muted); padding: 3rem; text-align: center; background: rgba(12,12,16,0.95); border-radius: 12px; border: 1px dashed rgba(255, 255, 255, 0.08); font-size: 0.85rem;">No reports available yet. Submit an analysis first.</div>';
            this.listContainer.className = '';
            return;
        }

        this.listContainer.innerHTML = '';
        this.listContainer.className = 'grid-cards';
        
        reports.forEach(report => {
            const el = document.createElement('div');
            el.className = 'card report-card';
            el.style.cursor = 'pointer';
            
            const dateStr = report.created_at ? new Date(report.created_at).toLocaleString() : new Date().toLocaleString();
            const title = report.title || 'Analysis Report';
            const competitor = report.competitor || 'Unknown Competitor';
            const confidence = report.confidence;
            const confidenceBadge = this.getConfidenceBadge(confidence);
            
            el.innerHTML = `
                <div class="card-header" style="margin-bottom: 1rem;">
                    ${title}
                    <div class="card-icon" style="background: rgba(255, 42, 42, 0.08); color: var(--accent);">
                        <i class="ph ph-file-text"></i>
                    </div>
                </div>
                <div style="color: var(--text-muted); font-size: 0.75rem; margin-bottom: 0.4rem;">
                    <span style="color: var(--text-muted); font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; font-size: 0.7rem;">Competitor</span>&nbsp;&nbsp;<span style="color: var(--text-main); font-weight: 500;">${competitor}</span>
                </div>
                <div style="color: var(--text-muted); font-size: 0.75rem; margin-bottom: 0.4rem; display: flex; align-items: center;">
                    <span style="color: var(--text-muted); font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; font-size: 0.7rem;">Confidence</span>&nbsp;&nbsp;${confidenceBadge}
                </div>
                <div style="color: var(--text-muted); font-size: 0.68rem; margin-top: 0.5rem;">
                    ${dateStr}
                </div>
                <div style="margin-top: 0.85rem; color: var(--accent-bright); font-size: 0.7rem; font-weight: 600; display: flex; align-items: center; gap: 0.25rem; text-transform: uppercase; letter-spacing: 0.05em;">
                    View Details <i class="ph ph-arrow-right"></i>
                </div>
            `;
            el.addEventListener('click', () => this.viewReport(report.id || report.report_id));
            this.listContainer.appendChild(el);
        });
    }

    async viewReport(id) {
        if (!this.detailContainer) return;
        
        try {
            this.listContainer.style.display = 'none';
            this.detailContainer.style.display = 'block';
            this.detailContainer.innerHTML = '<div class="loading" style="color: var(--text-muted); padding: 2rem; text-align: center;">Loading details...</div>';
            
            const response = await fetch(`http://localhost:8000/api/reports/${id}`);
            if (!response.ok) throw new Error('Failed to fetch report details');
            
            const report = await response.json();
            
            // Prioritize full_report_markdown, then fallback to other fields
            const markdownText = report.full_report_markdown || report.content || report.markdown || report.report || '# Empty Report';
            const contentHtml = marked.parse(markdownText);

            const confidenceBadge = this.getConfidenceBadge(report.confidence);
            
            this.detailContainer.innerHTML = `
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.5rem;">
                    <button class="btn-secondary" onclick="window.reportsManager.backToList()" style="background: rgba(255,255,255,0.05); color: var(--text-main); border: 1px solid var(--border-color); padding: 0.5rem 1rem; border-radius: 6px; cursor: pointer; display: flex; align-items: center; gap: 0.5rem; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; transition: all 0.2s;">
                        <i class="ph ph-arrow-left"></i> Back to list
                    </button>
                    ${confidenceBadge ? `<div style="display: flex; align-items: center; gap: 0.5rem;"><span style="color: var(--text-muted); font-size: 0.7rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;">Confidence</span>${confidenceBadge}</div>` : ''}
                </div>
                <div class="report-content" style="background: var(--card-bg); padding: 2.5rem; border-radius: 12px; border: 1px solid rgba(255,255,255,0.205); color: var(--text-main); line-height: 1.6;">
                    ${contentHtml}
                </div>
            `;
            
            if (!document.getElementById('report-markdown-styles')) {
                const style = document.createElement('style');
                style.id = 'report-markdown-styles';
                style.textContent = `
                    .report-content h1, .report-content h2, .report-content h3 { color: #fff; margin-top: 1.5rem; margin-bottom: 1rem; font-weight: 900; letter-spacing: -0.02em; }
                    .report-content h1 { font-size: 2rem; border-bottom: 1px solid var(--border-color); padding-bottom: 0.5rem; }
                    .report-content h2 { font-size: 1.5rem; }
                    .report-content p { margin-bottom: 1rem; color: var(--text-muted); line-height: 1.6; }
                    .report-content ul, .report-content ol { margin-left: 1.5rem; margin-bottom: 1rem; color: var(--text-muted); }
                    .report-content li { margin-bottom: 0.5rem; }
                    .report-content strong { color: var(--text-main); font-weight: 700; }
                    .report-content pre { background: rgba(0,0,0,0.4); padding: 1rem; border-radius: 8px; overflow-x: auto; margin-bottom: 1rem; border: 1px solid var(--border-color); }
                    .report-content code { font-family: monospace; color: var(--accent-bright); }
                    .report-content a { color: var(--accent-bright); text-decoration: none; }
                    .report-content a:hover { text-decoration: underline; }
                `;
                document.head.appendChild(style);
            }
        } catch (e) {
            console.error(e);
            this.detailContainer.innerHTML = `
                <button class="btn-secondary" onclick="window.reportsManager.backToList()" style="margin-bottom: 2rem; background: rgba(255,255,255,0.05); color: var(--text-main); border: 1px solid var(--border-color); padding: 0.5rem 1rem; border-radius: 6px; cursor: pointer; display: flex; align-items: center; gap: 0.5rem; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;">
                    <i class="ph ph-arrow-left"></i> Back to list
                </button>
                <div class="error" style="color: #ef4444; padding: 2rem; text-align: center; background: rgba(239, 68, 68, 0.1); border-radius: 12px;">Error loading details: ${e.message}</div>
            `;
        }
    }

    backToList() {
        this.detailContainer.style.display = 'none';
        this.listContainer.style.display = 'grid'; // Return to grid layout
        this.fetchReports(); // Refresh data
    }
}

function initReports() {
    window.reportsManager = new ReportsManager();
    window.reportsManager.fetchReports();
}
