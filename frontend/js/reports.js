// frontend/js/reports.js

class ReportsManager {
    constructor() {
        this.container = document.getElementById('page-reports');
        this.detailContainer = document.getElementById('report-detail');
        this.listContainer = document.getElementById('reports-list');
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
            this.listContainer.innerHTML = '<div class="empty-state" style="color: var(--text-muted); padding: 3rem; text-align: center; background: rgba(255,255,255,0.02); border-radius: 12px; border: 1px dashed rgba(255,255,255,0.1);">No reports available yet. Submit an analysis first.</div>';
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
            const confidence = report.confidence !== undefined ? report.confidence + '%' : 'N/A';
            
            el.innerHTML = `
                <div class="card-header" style="margin-bottom: 1rem;">
                    ${title}
                    <div class="card-icon" style="background: rgba(255, 42, 42, 0.08); color: var(--accent);">
                        <i class="ph ph-file-text"></i>
                    </div>
                </div>
                <div style="color: var(--text-muted); font-size: 0.85rem; margin-bottom: 0.5rem;">
                    <strong>Competitor:</strong> <span style="color: var(--text-main);">${competitor}</span>
                </div>
                <div style="color: var(--text-muted); font-size: 0.85rem; margin-bottom: 0.5rem;">
                    <strong>Confidence:</strong> <span style="color: var(--accent);">${confidence}</span>
                </div>
                <div style="color: var(--text-muted); font-size: 0.85rem;">
                    Generated: ${dateStr}
                </div>
                <div style="margin-top: 1rem; color: var(--accent); font-size: 0.85rem; font-weight: 500; display: flex; align-items: center; gap: 0.25rem;">
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
            
            const markdownText = report.content || report.markdown || report.report || '# Empty Report';
            const contentHtml = marked.parse(markdownText);
            
            this.detailContainer.innerHTML = `
                <button class="btn-secondary" onclick="window.reportsManager.backToList()" style="margin-bottom: 2rem; background: rgba(255,255,255,0.05); color: var(--text-main); border: 1px solid var(--border-color); padding: 0.5rem 1rem; border-radius: 8px; cursor: pointer; display: flex; align-items: center; gap: 0.5rem; transition: all 0.2s;">
                    <i class="ph ph-arrow-left"></i> Back to list
                </button>
                <div class="report-content" style="background: var(--card-bg); padding: 2.5rem; border-radius: 16px; border: 1px solid var(--border-color); color: var(--text-main); line-height: 1.6;">
                    ${contentHtml}
                </div>
            `;
            
            if (!document.getElementById('report-markdown-styles')) {
                const style = document.createElement('style');
                style.id = 'report-markdown-styles';
                style.textContent = `
                    .report-content h1, .report-content h2, .report-content h3 { color: #fff; margin-top: 1.5rem; margin-bottom: 1rem; }
                    .report-content h1 { font-size: 2rem; border-bottom: 1px solid var(--border-color); padding-bottom: 0.5rem; }
                    .report-content h2 { font-size: 1.5rem; }
                    .report-content p { margin-bottom: 1rem; color: var(--text-muted); }
                    .report-content ul, .report-content ol { margin-left: 1.5rem; margin-bottom: 1rem; color: var(--text-muted); }
                    .report-content li { margin-bottom: 0.5rem; }
                    .report-content strong { color: var(--text-main); }
                    .report-content pre { background: rgba(0,0,0,0.3); padding: 1rem; border-radius: 8px; overflow-x: auto; margin-bottom: 1rem; border: 1px solid var(--border-color); }
                    .report-content code { font-family: monospace; color: #a855f7; }
                `;
                document.head.appendChild(style);
            }
        } catch (e) {
            console.error(e);
            this.detailContainer.innerHTML = `
                <button class="btn-secondary" onclick="window.reportsManager.backToList()" style="margin-bottom: 2rem; background: rgba(255,255,255,0.05); color: var(--text-main); border: 1px solid var(--border-color); padding: 0.5rem 1rem; border-radius: 8px; cursor: pointer; display: flex; align-items: center; gap: 0.5rem;">
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
