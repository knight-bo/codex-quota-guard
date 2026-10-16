#!/usr/bin/env python3
"""Run the bundled core without pip, credentials, or host configuration changes."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from quota_guard.cli import main
if __name__ == '__main__':
    raise SystemExit(main())
