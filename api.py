"""
Vercel entry point for Vigil API.
Adds backend/ to sys.path so relative imports in backend/api.py work correctly.
"""
import sys
import os

# Add backend directory to Python path for relative imports
_backend_path = os.path.join(os.path.dirname(__file__), 'backend')
if _backend_path not in sys.path:
    sys.path.insert(0, _backend_path)

# Import the FastAPI app from backend/api.py using importlib to avoid circular imports
import importlib.util
_spec = importlib.util.spec_from_file_location("vigil_api", os.path.join(_backend_path, "api.py"))
_api_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_api_module)

# Export the FastAPI app instance
app = _api_module.app
