import os
import shutil
import re

moves = {
    "config.py": "core/config.py",
    "models/database.py": "core/database.py",
    "services/logger.py": "core/logger.py",
    "services/tracing.py": "core/tracing.py",
    "services/events.py": "core/events.py",
    "services/budget.py": "core/budget.py",

    "services/llm.py": "integrations/llm.py",
    "services/delivery.py": "integrations/delivery.py",
    "services/pdf_generator.py": "integrations/pdf_generator.py",

    "services/background.py": "pipeline/executor.py",
    "services/scheduler.py": "pipeline/scheduler.py",
    "services/checkpointer.py": "pipeline/checkpointer.py",
    "services/context.py": "pipeline/context.py",
    "services/profile_writer.py": "pipeline/profile_writer.py",
    "agents/profile_loader.py": "pipeline/profile_loader.py",

    "api/analyze.py": "api/routes/analyze.py",
    "api/competitors.py": "api/routes/competitors.py",
    "api/health.py": "api/routes/health.py",
    "api/reports.py": "api/routes/reports.py",
    "api/webhooks.py": "api/routes/webhooks.py",

    "agents/arbiter.py": "agents/nodes/arbiter.py",
    "agents/scout.py": "agents/nodes/scout.py",
    "agents/scribe.py": "agents/nodes/scribe.py",
    "agents/sentinel.py": "agents/nodes/sentinel.py",
    "agents/strategist.py": "agents/nodes/strategist.py",
    "agents/verifier.py": "agents/nodes/verifier.py",
}

imports_map = {
    "backend.core.config": "backend.core.config",
    "backend.core.database": "backend.core.database",
    "backend.core.logger": "backend.core.logger",
    "backend.core.tracing": "backend.core.tracing",
    "backend.core.events": "backend.core.events",
    "backend.core.budget": "backend.core.budget",

    "backend.integrations.llm": "backend.integrations.llm",
    "backend.integrations.delivery": "backend.integrations.delivery",
    "backend.integrations.pdf_generator": "backend.integrations.pdf_generator",

    "backend.pipeline.executor": "backend.pipeline.executor",
    "backend.pipeline.scheduler": "backend.pipeline.scheduler",
    "backend.pipeline.checkpointer": "backend.pipeline.checkpointer",
    "backend.pipeline.context": "backend.pipeline.context",
    "backend.pipeline.profile_writer": "backend.pipeline.profile_writer",
    "backend.pipeline.profile_loader": "backend.pipeline.profile_loader",

    "backend.api.routes.analyze": "backend.api.routes.analyze",
    "backend.api.routes.competitors": "backend.api.routes.competitors",
    "backend.api.routes.health": "backend.api.routes.health",
    "backend.api.routes.reports": "backend.api.routes.reports",
    "backend.api.routes.webhooks": "backend.api.routes.webhooks",

    "backend.agents.nodes.arbiter": "backend.agents.nodes.arbiter",
    "backend.agents.nodes.scout": "backend.agents.nodes.scout",
    "backend.agents.nodes.scribe": "backend.agents.nodes.scribe",
    "backend.agents.nodes.sentinel": "backend.agents.nodes.sentinel",
    "backend.agents.nodes.strategist": "backend.agents.nodes.strategist",
    "backend.agents.nodes.verifier": "backend.agents.nodes.verifier",
}

os.makedirs("core", exist_ok=True)
os.makedirs("integrations", exist_ok=True)
os.makedirs("pipeline", exist_ok=True)
os.makedirs("api/routes", exist_ok=True)
os.makedirs("agents/nodes", exist_ok=True)

with open("core/__init__.py", "w") as f: pass
with open("integrations/__init__.py", "w") as f: pass
with open("pipeline/__init__.py", "w") as f: pass
with open("api/routes/__init__.py", "w") as f: pass
with open("agents/nodes/__init__.py", "w") as f: pass

for src, dst in moves.items():
    if os.path.exists(src):
        print(f"Moving {src} to {dst}")
        shutil.move(src, dst)
    else:
        print(f"Warning: {src} not found")

if os.path.exists("tracing"):
    shutil.rmtree("tracing")

py_files = []
for root, _, files in os.walk(".."):
    if ".venv" in root or ".git" in root or ".pytest_cache" in root:
        continue
    for file in files:
        if file.endswith(".py"):
            py_files.append(os.path.join(root, file))

for py_file in py_files:
    with open(py_file, "r") as f:
        content = f.read()
    
    new_content = content
    for old_import in sorted(imports_map.keys(), key=len, reverse=True):
        new_import = imports_map[old_import]
        pattern = r'\b' + re.escape(old_import) + r'\b'
        new_content = re.sub(pattern, new_import, new_content)
    
    if new_content != content:
        print(f"Updating imports in {py_file}")
        with open(py_file, "w") as f:
            f.write(new_content)

print("Done refactoring.")
