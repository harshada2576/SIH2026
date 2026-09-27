#!/usr/bin/env python3
"""
generator.py — Root Unified Dataset Generator Launcher
SIH26184 — Predictive Cash Egress Interception
"""
import os
import sys

# Ensure data-generator is importable
repo_root = os.path.dirname(os.path.abspath(__file__))
data_gen_dir = os.path.join(repo_root, "data-generator")
if data_gen_dir not in sys.path:
    sys.path.insert(0, data_gen_dir)

from generate import main

if __name__ == "__main__":
    main()
