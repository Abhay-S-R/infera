// frontend/js/websocket.js

function initWebSocket() {
    const wsUrl = 'ws://127.0.0.1:8000/ws/activity';
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
                    
                    // Handle the nested format: {"type": "activity", "payload": {"agent": "scout", "status": "running", "message": "..."}}
                    let payload = data;
                    if (data.type === 'activity' && data.payload) {
                        payload = data.payload;
                    }

                    const eventType = data.type || payload.event_type || '';
                    if (window.addActivityEvent) {
                        window.addActivityEvent({ ...payload, event_type: eventType });
                    }

                    // Allow either node or agent key for pipeline status
                    const agentName = payload.agent || payload.node;
                    if (agentName && payload.status && typeof updatePipelineStatus === 'function') {
                        updatePipelineStatus(agentName, payload.status);
                    }
                    if (eventType === 'verifier.rejected' && typeof updatePipelineStatus === 'function') {
                        updatePipelineStatus('verifier', 'error');
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
