"""
Root entry point for Streamlit Community Cloud.
Dispatches directly to poc/app.py.
"""
import sys
from pathlib import Path

# Add poc directory to sys.path
poc_dir = Path(__file__).parent / "poc"
if str(poc_dir) not in sys.path:
    sys.path.insert(0, str(poc_dir))

# Execute poc/app.py
app_path = poc_dir / "app.py"
with open(app_path, "r", encoding="utf-8") as f:
    code = compile(f.read(), str(app_path), "exec")
    exec(code, {"__name__": "__main__", "__file__": str(app_path)})
