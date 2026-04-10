"""
Shared pytest fixtures for AutoPitch tests.
"""

import os
import sys

# Ensure project root is on sys.path so imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))