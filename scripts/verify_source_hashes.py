#!/usr/bin/env python3
"""Check hashes of source archives that materialize_sources.py has already written."""
from __future__ import annotations

import runpy
import sys
from pathlib import Path

SCRIPT = Path(__file__).with_name("materialize_sources.py")
sys.argv = [str(SCRIPT), "--check", *sys.argv[1:]]
runpy.run_path(str(SCRIPT), run_name="__main__")
