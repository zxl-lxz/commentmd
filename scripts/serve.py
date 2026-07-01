#!/usr/bin/env python3
"""commentmd - open a browser for the user to comment on a Markdown file."""

import hashlib
from pathlib import Path


def compute_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


import socket


def find_free_port(start: int, end: int) -> int:
    for port in range(start, end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise RuntimeError(f"No free port in [{start}, {end}]")


import json


def build_page_data(md_path: Path) -> dict:
    md_path = md_path.resolve()
    content = md_path.read_text(encoding="utf-8")
    return {
        "md_file": str(md_path),
        "md_name": md_path.name,
        "md_content": content,
        "md_sha256": compute_sha256(md_path),
    }


def resolve_output_path(md_path: Path, out_arg):
    if out_arg is not None:
        return out_arg
    return md_path.with_suffix(".comments.json")


_SENTINEL = "/* __DATA_INJECTION__ */"


def inject_template(html_template: str, data: dict, mode: str) -> str:
    # json.dumps escapes </ so a literal </script> can't leak into the JS
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    mode_js = json.dumps(mode)
    block = f'window.__DATA__ = {payload};\nwindow.__MODE__ = {mode_js};'
    if _SENTINEL in html_template:
        return html_template.replace(_SENTINEL, block)
    injection = f'<script>\n{block}\n</script>\n</head>'
    return html_template.replace("</head>", injection, 1)
