import sys

def fix_file(path):
    with open(path, 'r') as f:
        lines = f.readlines()
        
    out = []
    unindent = False
    for line in lines:
        if "budget = get_budget(state)" in line and line.startswith("        budget"):
            unindent = True
            
        if unindent and line.startswith("    "):
            out.append(line[4:])
        elif unindent and line == "\n":
            out.append(line)
        else:
            out.append(line)
            
    with open(path, 'w') as f:
        f.writelines(out)

for path in ['backend/agents/sentinel.py', 'backend/agents/scout.py', 'backend/agents/scribe.py', 'backend/agents/arbiter.py']:
    fix_file(path)
