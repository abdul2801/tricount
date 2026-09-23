"""WSGI entry point for PythonAnywhere deployment."""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run()
