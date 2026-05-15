// frontend/js/websocket.js

function initWebSocket() {
    const wsUrl = 'ws://localhost:8000/ws/activity';
    let socket;
    const feedContainer = document.getElementById('activity-feed');

    if (!feedContainer) {
        console.error('Activity feed container not found.');
        return;
    }

    function connect() {
        try {
            socket = new WebSocket(wsUrl);

            socket.onopen = () => {
                console.log('WebSocket connection established');
                logActivity({ type: 'system', message: 'Connected to activity stream', timestamp: new Date().toISOString() });
            };

            socket.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    logActivity(data);
                    
                    // If event has pipeline status info, update pipeline
                    // Format assumption: { node: 'Scout', status: 'active' }
                    if (data.node && data.status && typeof updatePipelineStatus === 'function') {
                        updatePipelineStatus(data.node, data.status);
                    }
                } catch (e) {
                    console.error('Error parsing WebSocket message', e);
                }
            };

            socket.onclose = () => {
                console.log('WebSocket connection closed. Reconnecting in 5s...');
                setTimeout(connect, 5000);
            };

            socket.onerror = (error) => {
                console.error('WebSocket error:', error);
                socket.close();
            };
        } catch (e) {
            console.error('Failed to connect to WebSocket:', e);
        }
    }

    function logActivity(activity) {
        if (!feedContainer) return;

        const item = document.createElement('div');
        item.style.padding = '0.75rem';
        item.style.borderRadius = '8px';
        item.style.background = 'rgba(255, 255, 255, 0.05)';
        item.style.borderLeft = '4px solid var(--accent)';
        item.style.fontSize = '0.875rem';
        item.style.color = 'var(--text-main)';
        item.style.display = 'flex';
        item.style.flexDirection = 'column';
        item.style.gap = '0.25rem';
        
        let timeString = '';
        if (activity.timestamp) {
            const date = new Date(activity.timestamp);
            timeString = date.toLocaleTimeString();
        } else {
            timeString = new Date().toLocaleTimeString();
        }
        
        const header = document.createElement('div');
        header.style.display = 'flex';
        header.style.justifyContent = 'space-between';
        header.style.alignItems = 'center';
        header.innerHTML = `
            <strong>${activity.type || 'Event'}</strong>
            <span style="color: var(--text-muted); font-family: monospace; font-size: 0.75rem;">${timeString}</span>
        `;
        
        const message = document.createElement('div');
        message.style.color = 'var(--text-muted)';
        message.textContent = activity.message || JSON.stringify(activity);

        item.appendChild(header);
        item.appendChild(message);
        
        feedContainer.prepend(item);
        
        // Keep feed from growing infinitely
        if (feedContainer.children.length > 50) {
            feedContainer.removeChild(feedContainer.lastChild);
        }
    }

    connect();
}
