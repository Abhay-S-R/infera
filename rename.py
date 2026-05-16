import os
import re

def replace_in_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Simple replacement for all three cases
    new_content = content.replace("INFERA", "INFERA")
    new_content = new_content.replace("Infera", "Infera")
    new_content = new_content.replace("infera", "infera")
    
    if new_content != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Updated {filepath}")

def process_directory(dirpath):
    for root, dirs, files in os.walk(dirpath):
        if '.git' in dirs:
            dirs.remove('.git')
        if '.venv' in dirs:
            dirs.remove('.venv')
        if '__pycache__' in dirs:
            dirs.remove('__pycache__')
        if '.pytest_cache' in dirs:
            dirs.remove('.pytest_cache')
            
        for file in files:
            if file.endswith(('.py', '.md', '.txt', '.html', '.yml', '.yaml', '.example', '.sh')) or file == '.env':
                filepath = os.path.join(root, file)
                try:
                    replace_in_file(filepath)
                except Exception as e:
                    print(f"Failed to process {filepath}: {e}")

if __name__ == "__main__":
    process_directory(".")
