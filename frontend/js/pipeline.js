// frontend/js/pipeline.js

function initPipeline() {
    const nodes = ['Sentinel', 'Verifier', 'Scout', 'Strategist', 'Arbiter', 'Scribe'];
    
    // Status color mapping
    const statusColors = {
        'idle': '#64748b', // gray
        'running': '#FF2A2A', // red (matches theme)
        'active': '#FF2A2A', // red (matches theme)
        'done': '#10b981', // green
        'error': '#ef4444', // red error
        'retry': '#f97316' // orange
    };
    
    const container = document.getElementById('pipeline-container');
    if (!container) return;

    // Setup container styles
    container.style.background = 'rgba(12, 12, 16, 0.95)';
    container.style.border = '1px solid rgba(255, 255, 255, 0.205)';
    container.style.borderRadius = '12px';
    container.style.padding = '2.5rem 2rem';
    container.style.marginBottom = '1.5rem';
    container.style.display = 'flex';
    container.style.alignItems = 'center';
    container.style.justifyContent = 'space-between';
    container.style.position = 'relative';

    const nodeElements = {};

    nodes.forEach((node, index) => {
        const nodeWrapper = document.createElement('div');
        nodeWrapper.style.display = 'flex';
        nodeWrapper.style.alignItems = 'center';
        nodeWrapper.style.flex = index === nodes.length - 1 ? '0 0 auto' : '1';
        nodeWrapper.style.position = 'relative';

        const nodeInner = document.createElement('div');
        nodeInner.style.display = 'flex';
        nodeInner.style.flexDirection = 'column';
        nodeInner.style.alignItems = 'center';
        nodeInner.style.gap = '0.75rem';
        nodeInner.style.zIndex = '2';

        const circle = document.createElement('div');
        circle.className = `pipeline-node ${node.toLowerCase()}`;
        const nodeSize = nodes.length > 5 ? '40px' : '48px';
        circle.style.width = nodeSize;
        circle.style.height = nodeSize;
        circle.style.borderRadius = '50%';
        circle.style.background = statusColors['idle']; // default
        circle.style.border = '3px solid #0a0a0d';
        circle.style.boxShadow = '0 0 10px rgba(0,0,0,0.3)';
        circle.style.display = 'flex';
        circle.style.alignItems = 'center';
        circle.style.justifyContent = 'center';
        circle.style.color = '#fff';
        circle.style.fontWeight = '900';
        circle.style.fontSize = nodes.length > 5 ? '0.65rem' : '0.8rem';
        circle.style.letterSpacing = '0.05em';
        circle.style.transition = 'all 0.4s ease';
        
        // Add number inside
        circle.textContent = (index + 1).toString();

        const label = document.createElement('div');
        label.textContent = node;
        label.style.fontWeight = '600';
        label.style.fontSize = '0.7rem';
        label.style.color = 'rgba(255, 255, 255, 0.45)';
        label.style.letterSpacing = '0.05em';
        label.style.textTransform = 'uppercase';

        nodeInner.appendChild(circle);
        nodeInner.appendChild(label);
        nodeWrapper.appendChild(nodeInner);

        // Add arrow to next node
        if (index < nodes.length - 1) {
            const arrowContainer = document.createElement('div');
            arrowContainer.style.flex = '1';
            arrowContainer.style.height = '2px';
            arrowContainer.style.background = 'rgba(255, 42, 42, 0.15)';
            arrowContainer.style.margin = '0 -10px 30px -10px';
            arrowContainer.style.position = 'relative';
            arrowContainer.style.zIndex = '1';

            const arrowHead = document.createElement('div');
            arrowHead.style.position = 'absolute';
            arrowHead.style.right = '0';
            arrowHead.style.top = '-4px';
            arrowHead.style.width = '0'; 
            arrowHead.style.height = '0'; 
            arrowHead.style.borderTop = '5px solid transparent';
            arrowHead.style.borderBottom = '5px solid transparent';
            arrowHead.style.borderLeft = '8px solid rgba(255, 42, 42, 0.25)';
            
            arrowContainer.appendChild(arrowHead);
            nodeWrapper.appendChild(arrowContainer);
        }

        container.appendChild(nodeWrapper);
        nodeElements[node.toLowerCase()] = circle;
    });

    // Create curved arrow for retry (Arbiter to Scout)
    const retryArrow = document.createElement('div');
    retryArrow.id = 'retry-arrow';
    retryArrow.style.position = 'absolute';
    retryArrow.style.top = '15px';
    retryArrow.style.left = '32%'; // Start around Scout
    retryArrow.style.width = '36%'; // End around Arbiter
    retryArrow.style.height = '40px';
    retryArrow.style.borderTop = '2px dashed #f97316';
    retryArrow.style.borderLeft = '2px dashed transparent';
    retryArrow.style.borderRight = '2px dashed transparent';
    retryArrow.style.borderBottom = 'none';
    retryArrow.style.borderRadius = '50% 50% 0 0 / 100% 100% 0 0';
    retryArrow.style.zIndex = '1';
    retryArrow.style.opacity = '0';
    retryArrow.style.transition = 'opacity 0.3s ease';
    retryArrow.style.pointerEvents = 'none';
    
    // Add arrowhead pointing left
    const head = document.createElement('div');
    head.style.position = 'absolute';
    head.style.bottom = '-6px';
    head.style.left = '-6px';
    head.style.width = '0';
    head.style.height = '0';
    head.style.borderTop = '8px solid #f97316';
    head.style.borderLeft = '8px solid transparent';
    head.style.borderRight = '8px solid transparent';
    head.style.transform = 'rotate(-45deg)';
    retryArrow.appendChild(head);
    
    container.appendChild(retryArrow);

    window.updatePipelineStatus = function(nodeName, status) {
        let nodeKey = nodeName.toLowerCase();
        if (nodeKey === 'profile_loader' || nodeKey === 'profileloader') {
            nodeKey = 'sentinel';
        }
        
        // Reset all nodes to idle initially if it's Sentinel running (new run)
        if (nodeKey === 'sentinel' && (status === 'running' || status === 'active')) {
            Object.values(nodeElements).forEach(el => {
                el.style.background = statusColors['idle'];
                el.classList.remove('pulse-animation');
                el.classList.remove('pulse-animation-orange');
                el.style.boxShadow = '0 0 10px rgba(0,0,0,0.3)';
                el.style.transform = 'scale(1)';
            });
            const arrow = document.getElementById('retry-arrow');
            if (arrow) arrow.style.opacity = '0';
        }

        if (nodeElements[nodeKey] && statusColors[status]) {
            const el = nodeElements[nodeKey];
            el.style.background = statusColors[status];
            
            el.classList.remove('pulse-animation');
            el.classList.remove('pulse-animation-orange');
            
            if (status === 'running' || status === 'active') {
                el.classList.add('pulse-animation');
                el.style.transform = 'scale(1.1)';
            } else if (status === 'retry') {
                el.classList.add('pulse-animation-orange');
                el.style.transform = 'scale(1.1)';
            } else {
                el.style.boxShadow = '0 0 10px rgba(0,0,0,0.3)';
                el.style.transform = 'scale(1)';
            }
        }
        
        // Handle retry specific animation
        const arrow = document.getElementById('retry-arrow');
        if (arrow) {
            if (status === 'retry' && nodeKey === 'arbiter') {
                arrow.style.opacity = '1';
                
                // Set Scout to active visually since it's retrying
                if (nodeElements['scout']) {
                    nodeElements['scout'].style.background = statusColors['running'];
                    nodeElements['scout'].classList.add('pulse-animation');
                }
            } else if (status === 'done' && nodeKey === 'arbiter') {
                arrow.style.opacity = '0';
            }
        }
    };
}
