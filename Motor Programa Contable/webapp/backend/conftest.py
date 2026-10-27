import os
import sys
import pytest

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
COMPAT_DIR = os.path.join(BACKEND_DIR, "compat")

for p in [BACKEND_DIR, COMPAT_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

import db_manager

@pytest.fixture(autouse=True)
def setup_test_db():
    """Ensure clean schema is initialized before running tests."""
    db_manager.init_db()
