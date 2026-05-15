// frontend/js/activity.js

function addActivityEvent(data) {
    const feedContainer = document.getElementById('activity-feed');
    if (!feedContainer) return;

    const item = document.createElement('div');
    item.className = 'activity-item slide-in';
    
    let statusClass = 'status-default';
    if (data.status === 'active' || data.status === 'running') statusClass = 'status-active';
    else if (data.status === 'done' || data.status === 'success') statusClass = 'status-success';
    else if (data.status === 'error' || data.status === 'failed') statusClass = 'status-error';
    else if (data.status === 'idle') statusClass = 'status-idle';

    const timeString = data.timestamp 
        ? new Date(data.timestamp).toLocaleTimeString() 
        : new Date().toLocaleTimeString();

    const agentName = data.agent || data.node || 'System';

    item.innerHTML = `
        <div class="activity-header" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
            <div class="activity-agent" style="display: flex; align-items: center; gap: 0.5rem;">
                <span class="status-indicator ${statusClass}"></span>
                <strong style="color: var(--text-main); font-size: 0.95rem;">${agentName}</strong>
                ${data.status ? `<span class="badge ${statusClass}">${data.status}</span>` : ''}
            </div>
            <span class="activity-time" style="color: var(--text-muted); font-size: 0.75rem; font-family: monospace;">${timeString}</span>
        </div>
        <div class="activity-body" style="color: var(--text-muted); font-size: 0.85rem; line-height: 1.4;">
            ${data.message || JSON.stringify(data)}
        </div>
    `;

    feedContainer.prepend(item);

    if (feedContainer.children.length > 50) {
        feedContainer.removeChild(feedContainer.lastChild);
    }
}
