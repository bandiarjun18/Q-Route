"""
conftest.py – project-root pytest configuration.

Inserts the backend/ directory onto sys.path so that `import app.*`
works when pytest is invoked from the backend/ directory.
"""
import sys
from pathlib import Path

# backend/ directory (where this file lives)
sys.path.insert(0, str(Path(__file__).parent))
