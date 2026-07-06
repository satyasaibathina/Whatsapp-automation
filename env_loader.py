"""
env_loader.py
Parses the local .env file and populates os.environ.
"""
import os

try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(script_dir, '.env')
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                trimmed_line = line.strip()
                if not trimmed_line or trimmed_line.startswith('#'):
                    continue
                
                equal_idx = trimmed_line.find('=')
                if equal_idx > 0:
                    key = trimmed_line[:equal_idx].strip()
                    val = trimmed_line[equal_idx + 1:].strip()
                    
                    # Remove enclosing single/double quotes if present
                    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                        val = val[1:-1]
                    
                    if key:
                        os.environ[key] = val
except Exception as err:
    print(f"⚠️ Warning: Failed to load .env file: {err}")
