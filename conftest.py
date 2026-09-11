"""Make the repo root importable so tests can `import shared / pipeline / detection`."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))