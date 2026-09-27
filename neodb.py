#!/usr/bin/env python3
"""Run the converter without installation: python3 neodb.py igo -i ... -o ..."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from openneodb.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
