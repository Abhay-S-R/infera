import re

def fix_agent(path, agent_name):
    with open(path, 'r') as f:
        content = f.read()

    # Replace import
    content = content.replace("from backend.services.tracing import get_tracer", "from backend.services.tracing import trace_agent")
    
    # Add decorator
    content = re.sub(r'async def ' + agent_name + r'_node', '@trace_agent("' + agent_name + '")\nasync def ' + agent_name + '_node', content)
    
    # Remove tracer lines
    lines = content.split('\n')
    out = []
    in_with = False
    for line in lines:
        if line.strip() == "tracer = get_tracer()":
            continue
        if line.strip().startswith("with tracer.start_span"):
            in_with = True
            continue
            
        if in_with and line.startswith("        "):
            out.append(line[4:])
        elif in_with and line == "":
            out.append(line)
        else:
            in_with = False
            out.append(line)
            
    with open(path, 'w') as f:
        f.write('\n'.join(out))

fix_agent('backend/agents/sentinel.py', 'sentinel')
fix_agent('backend/agents/scout.py', 'scout')
fix_agent('backend/agents/scribe.py', 'scribe')
fix_agent('backend/agents/arbiter.py', 'arbiter')
