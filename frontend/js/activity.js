// frontend/js/activity.js

function addActivityEvent(data) {
    const feedContainer = document.getElementById('activity-feed');
    if (!feedContainer) return;

    const item = document.createElement('div');
    item.className = 'activity-item slide-in';
    
    let statusClass = 'status-default';
    if (data.status === 'active' || data.status === 'running') statusClass = 'status-running';
    else if (data.status === 'done' || data.status === 'success') statusClass = 'status-success';
    else if (data.status === 'error' || data.status === 'failed') statusClass = 'status-error';
    else if (data.status === 'retry') statusClass = 'status-retry';
    else if (data.status === 'idle') statusClass = 'status-idle';

    const timeString = data.timestamp 
        ? new Date(data.timestamp).toLocaleTimeString() 
        : new Date().toLocaleTimeString();

    const agentName = data.agent || data.node || 'System';

    const displayStatus = data.status ? data.status.charAt(0).toUpperCase() + data.status.slice(1) : '';

    item.innerHTML = `
        <div class="activity-header" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.35rem;">
            <div class="activity-agent" style="display: flex; align-items: center; gap: 0.4rem;">
                <span class="status-indicator ${statusClass}"></span>
                <strong style="color: var(--text-main); font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 600;">${agentName}</strong>
                ${displayStatus ? `<span class="badge ${statusClass}">${displayStatus}</span>` : ''}
            </div>
            <span class="activity-time" style="color: var(--text-muted); font-size: 0.68rem; font-weight: 500; font-variant-numeric: tabular-nums;">${timeString}</span>
        </div>
        <div class="activity-body" style="color: var(--text-muted); font-size: 0.85rem; line-height: 1.6;">
            ${data.message || JSON.stringify(data)}
        </div>
    `;

    // Append to bottom
    feedContainer.appendChild(item);

    // Auto-scroll to latest
    feedContainer.scrollTop = feedContainer.scrollHeight;

    // Keep max 100 items
    if (feedContainer.children.length > 100) {
        feedContainer.removeChild(feedContainer.firstChild);
    }
}
