// frontend/js/websocket.js

function initWebSocket() {
    const wsUrl = 'ws://localhost:8000/ws/activity';
    let socket;
    
    function connect() {
        try {
            socket = new WebSocket(wsUrl);

            socket.onopen = () => {
                console.log('WebSocket connection established');
                if (window.addActivityEvent) {
                    window.addActivityEvent({ agent: 'System', status: 'success', message: 'Connected to activity stream', timestamp: new Date().toISOString() });
                }
            };

            socket.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    
                    if (window.addActivityEvent) {
                        window.addActivityEvent(data);
                    }
                    
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

    connect();
}
