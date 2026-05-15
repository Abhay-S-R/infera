// frontend/js/pipeline.js

function initPipeline() {
    const nodes = ['Sentinel', 'Scout', 'Strategist', 'Arbiter', 'Scribe'];
    const statuses = ['idle', 'active', 'done', 'error'];
    
    // Status color mapping
    const statusColors = {
        'idle': 'rgba(255, 255, 255, 0.1)',
        'active': 'var(--accent)',
        'done': '#10b981',
        'error': '#ef4444'
    };
    
    const container = document.getElementById('pipeline-container');
    if (!container) return;

    // Setup container styles
    container.style.background = 'var(--card-bg)';
    container.style.border = '1px solid var(--border-color)';
    container.style.borderRadius = '16px';
    container.style.padding = '2rem';
    container.style.marginBottom = '2rem';
    container.style.display = 'flex';
    container.style.alignItems = 'center';
    container.style.justifyContent = 'space-between';
    container.style.position = 'relative';
    container.style.backdropFilter = 'blur(10px)';

    // Add connector line behind nodes
    const line = document.createElement('div');
    line.style.position = 'absolute';
    line.style.top = '40%';
    line.style.left = '10%';
    line.style.right = '10%';
    line.style.height = '4px';
    line.style.background = 'rgba(255, 255, 255, 0.1)';
    line.style.transform = 'translateY(-50%)';
    line.style.zIndex = '0';
    container.appendChild(line);

    const nodeElements = {};

    nodes.forEach((node, index) => {
        const nodeWrapper = document.createElement('div');
        nodeWrapper.style.display = 'flex';
        nodeWrapper.style.flexDirection = 'column';
        nodeWrapper.style.alignItems = 'center';
        nodeWrapper.style.gap = '0.75rem';
        nodeWrapper.style.zIndex = '1';
        nodeWrapper.style.flex = '1';

        const circle = document.createElement('div');
        circle.className = `pipeline-node ${node.toLowerCase()}`;
        circle.style.width = '48px';
        circle.style.height = '48px';
        circle.style.borderRadius = '50%';
        circle.style.background = statusColors['idle']; // default
        circle.style.border = '4px solid var(--card-bg)';
        circle.style.boxShadow = '0 0 10px rgba(0,0,0,0.3)';
        circle.style.display = 'flex';
        circle.style.alignItems = 'center';
        circle.style.justifyContent = 'center';
        circle.style.color = '#fff';
        circle.style.fontWeight = 'bold';
        circle.style.transition = 'all 0.4s ease';
        
        // Add number inside
        circle.textContent = (index + 1).toString();

        const label = document.createElement('div');
        label.textContent = node;
        label.style.fontWeight = '500';
        label.style.fontSize = '0.9rem';
        label.style.color = 'var(--text-main)';

        nodeWrapper.appendChild(circle);
        nodeWrapper.appendChild(label);
        container.appendChild(nodeWrapper);
        
        nodeElements[node.toLowerCase()] = circle;
    });

    // Provide a global method to update node status
    window.updatePipelineStatus = function(nodeName, status) {
        const nodeKey = nodeName.toLowerCase();
        if (nodeElements[nodeKey] && statusColors[status]) {
            const el = nodeElements[nodeKey];
            el.style.background = statusColors[status];
            
            // Add glow if active or error
            if (status === 'active') {
                el.style.boxShadow = `0 0 20px ${statusColors[status]}`;
                el.style.transform = 'scale(1.1)';
            } else if (status === 'error') {
                el.style.boxShadow = `0 0 20px ${statusColors[status]}`;
                el.style.transform = 'scale(1)';
            } else {
                el.style.boxShadow = '0 0 10px rgba(0,0,0,0.3)';
                el.style.transform = 'scale(1)';
            }
        }
    };
}
