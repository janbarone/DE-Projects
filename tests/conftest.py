"""Shared test fixtures: put repo-local modules on sys.path."""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "data"))
sys.path.insert(0, str(REPO / "scripts"))
