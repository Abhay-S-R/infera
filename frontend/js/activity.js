// frontend/js/activity.js

function normalizeActivityPayload(raw) {
    if (!raw || typeof raw !== 'object') return raw;

    // WebSocket wraps Redis: { type, data: { agent, status, message, ... } }
    if (raw.data && typeof raw.data === 'object' && (raw.data.agent || raw.data.message)) {
        return { ...raw.data, event_type: raw.type || raw.data.event_type };
    }
    return { ...raw, event_type: raw.type || raw.event_type };
}

function isArbiterRejection(data) {
    if (!data) return false;
    const agent = (data.agent || data.node || '').toLowerCase();
    const status = (data.status || '').toLowerCase();
    const eventType = (data.event_type || '').toLowerCase();
    const message = (data.message || '').toLowerCase();

    if (eventType === 'arbiter.rejected') return true;
    if (agent === 'arbiter' && (status === 'rejected' || status === 'retry')) return true;
    if (agent === 'arbiter' && message.includes('rejected')) return true;
    return false;
}

function isVerifierRejection(data) {
    if (!data) return false;
    const agent = (data.agent || data.node || '').toLowerCase();
    const eventType = (data.event_type || '').toLowerCase();
    const message = (data.message || '').toLowerCase();

    if (eventType === 'verifier.rejected') return true;
    if (agent === 'verifier' && (data.status === 'error' || message.includes('unverified'))) return true;
    return false;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text == null ? '' : String(text);
    return div.innerHTML;
}

function addActivityEvent(rawData) {
    const feedContainer = document.getElementById('activity-feed');
    if (!feedContainer) return;

    const data = normalizeActivityPayload(rawData);
    const arbiterRejection = isArbiterRejection(data);
    const verifierRejection = isVerifierRejection(data);
    const rejection = arbiterRejection || verifierRejection;

    const item = document.createElement('div');
    item.className = 'activity-item slide-in';
    if (rejection) {
        item.classList.add('activity-rejection-alert');
    }

    let statusClass = 'status-default';
    if (data.status === 'active' || data.status === 'running') statusClass = 'status-running';
    else if (data.status === 'done' || data.status === 'success') statusClass = 'status-success';
    else if (data.status === 'error' || data.status === 'failed') statusClass = 'status-error';
    else if (data.status === 'retry' || data.status === 'rejected') statusClass = 'status-retry';
    else if (data.status === 'idle') statusClass = 'status-idle';

    const timeString = data.timestamp
        ? new Date(data.timestamp).toLocaleTimeString()
        : new Date().toLocaleTimeString();

    const agentName = data.agent || data.node || 'System';
    const displayStatus = data.status
        ? data.status.charAt(0).toUpperCase() + data.status.slice(1)
        : '';

    let rejectionBanner = '';
    if (verifierRejection) {
        rejectionBanner = `<div class="rejection-banner verifier-rejection" role="alert">
                <i class="ph ph-shield-warning"></i>
                <strong>VERIFIER HALTED PIPELINE</strong>
                <span>Signal failed primary-source verification</span>
           </div>`;
    } else if (arbiterRejection) {
        rejectionBanner = `<div class="rejection-banner" role="alert">
                <i class="ph ph-warning-octagon"></i>
                <strong>ARBITER REJECTED ANALYSIS</strong>
                <span>Pipeline sent back to Scout for re-research</span>
           </div>`;
    }

    const detailHtml = data.detail
        ? '<div class="activity-detail">' + escapeHtml(data.detail) + '</div>'
        : '';

    item.innerHTML = `
        ${rejectionBanner}
        <div class="activity-header" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.35rem;">
            <div class="activity-agent" style="display: flex; align-items: center; gap: 0.4rem;">
                <span class="status-indicator ${statusClass}"></span>
                <strong style="color: var(--text-main); font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 600;">${escapeHtml(agentName)}</strong>
                ${displayStatus ? `<span class="badge ${statusClass}">${escapeHtml(displayStatus)}</span>` : ''}
            </div>
            <span class="activity-time" style="color: var(--text-muted); font-size: 0.68rem; font-weight: 500; font-variant-numeric: tabular-nums;">${timeString}</span>
        </div>
        <div class="activity-body" style="color: var(--text-muted); font-size: 0.85rem; line-height: 1.6;">
            ${escapeHtml(data.message || '')}
        </div>
        ${detailHtml}
    `;

    feedContainer.appendChild(item);
    feedContainer.scrollTop = feedContainer.scrollHeight;

    if (feedContainer.children.length > 100) {
        feedContainer.removeChild(feedContainer.firstChild);
    }
}

window.addActivityEvent = addActivityEvent;
