"""The ONLY package permitted to touch MongoDB directly.

A test (tests/test_repo_boundary.py) fails if raw DB access appears elsewhere.
"""
from . import store  # noqa: F401
