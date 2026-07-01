#!/usr/bin/env python3
"""commentmd - open a browser for the user to comment on a Markdown file."""

import hashlib
from pathlib import Path


def compute_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
