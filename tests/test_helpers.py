import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

_SKILL_ROOT = Path(__file__).resolve().parent.parent / "skills" / "commentmd"
if str(_SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(_SKILL_ROOT))

from scripts.serve import compute_sha256


class ComputeSha256Tests(unittest.TestCase):
    def test_matches_stdlib_hash(self):
        fixture = Path(__file__).parent / "fixtures" / "sample.md"
        expected = hashlib.sha256(fixture.read_bytes()).hexdigest()
        self.assertEqual(compute_sha256(fixture), expected)


import socket

from scripts.serve import find_free_port


class FindFreePortTests(unittest.TestCase):
    def test_returns_start_when_free(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            _, free_port = s.getsockname()
        self.assertEqual(find_free_port(free_port, free_port), free_port)

    def test_skips_busy_port(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as busy:
            busy.bind(("127.0.0.1", 0))
            _, busy_port = busy.getsockname()
            busy.listen(1)
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                probe.bind(("127.0.0.1", 0))
                _, next_free = probe.getsockname()
            lo, hi = sorted((busy_port, next_free))
            result = find_free_port(lo, hi)
            self.assertNotEqual(result, busy_port)
            self.assertTrue(lo <= result <= hi)

    def test_raises_when_all_busy(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as busy:
            busy.bind(("127.0.0.1", 0))
            _, busy_port = busy.getsockname()
            busy.listen(1)
            with self.assertRaises(RuntimeError):
                find_free_port(busy_port, busy_port)


import json

from scripts.serve import build_page_data, resolve_output_path, inject_template


class BuildPageDataTests(unittest.TestCase):
    def test_returns_expected_keys(self):
        fixture = Path(__file__).parent / "fixtures" / "sample.md"
        data = build_page_data(fixture)
        self.assertEqual(data["md_name"], "sample.md")
        self.assertEqual(data["md_file"], str(fixture.resolve()))
        self.assertIn("# 技术方案示例", data["md_content"])
        self.assertEqual(len(data["md_sha256"]), 64)


class ResolveOutputPathTests(unittest.TestCase):
    def test_default_replaces_suffix(self):
        p = Path("/tmp/plan.md")
        self.assertEqual(resolve_output_path(p, None), Path("/tmp/plan.comments.json"))

    def test_explicit_out_wins(self):
        p = Path("/tmp/plan.md")
        override = Path("/tmp/x.json")
        self.assertEqual(resolve_output_path(p, override), override)


class InjectTemplateTests(unittest.TestCase):
    def test_replaces_sentinel(self):
        html = "<html><head><script>/* __DATA_INJECTION__ */</script></head></html>"
        out = inject_template(html, {"md_name": "x"}, "server")
        self.assertIn('window.__DATA__ =', out)
        self.assertIn('"md_name": "x"', out)
        self.assertIn('window.__MODE__ = "server"', out)
        self.assertNotIn("__DATA_INJECTION__", out)

    def test_falls_back_to_head_close(self):
        html = "<html><head></head><body></body></html>"
        out = inject_template(html, {"md_name": "x"}, "static")
        self.assertIn('window.__MODE__ = "static"', out)
        self.assertLess(out.index("window.__DATA__"), out.index("</head>"))

    def test_data_json_encodes_specials(self):
        html = "<html><head></head></html>"
        out = inject_template(html, {"md_content": "</script>"}, "server")
        head_close = out.index("</head>")
        pre = out[:head_close]
        # The escaped form must appear (proves payload escaping ran)
        self.assertIn("<\\/script>", pre)
        # The unescaped payload literal must NOT appear before </head>
        # (find the wrapper open, then check no </script> occurs between the
        #  wrapper open and its matching close in a way that would truncate).
        # Concretely: the substring "</script>" appears exactly once before
        # </head> — that's our own wrapper closer, not a payload injection.
        self.assertEqual(pre.count("</script>"), 1)


from scripts.serve import write_output_json


class WriteOutputJsonTests(unittest.TestCase):
    def test_writes_schema_and_counts_when_sha_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "a.comments.json"
            payload = {
                "comments": [
                    {"id": "c1", "quote": "q", "prefix": "", "suffix": "", "comment": "hi",
                     "created_at": "2026-07-01T00:00:00Z"},
                ],
            }
            result = write_output_json(payload, out, md_file="/x/a.md", md_sha256_initial="abc", md_sha256_current="abc")
            written = json.loads(out.read_text())
            self.assertEqual(written["schema_version"], 1)
            self.assertEqual(written["comment_count"], 1)
            self.assertFalse(written["md_changed_during_review"])
            self.assertEqual(written["md_file"], "/x/a.md")
            self.assertEqual(written["md_sha256"], "abc")
            self.assertEqual(written["comments"][0]["quote"], "q")
            self.assertEqual(result, written)

    def test_flags_sha_mismatch_when_current_differs(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "a.comments.json"
            payload = {"comments": []}
            write_output_json(payload, out, md_file="/x/a.md", md_sha256_initial="abc", md_sha256_current="def")
            written = json.loads(out.read_text())
            self.assertTrue(written["md_changed_during_review"])
            self.assertEqual(written["comment_count"], 0)

    def test_detects_real_file_mutation(self):
        """End-to-end: capture sha, mutate file, re-hash, verify flag is True."""
        with tempfile.TemporaryDirectory() as tmp:
            md = Path(tmp) / "plan.md"
            md.write_text("# original\n", encoding="utf-8")
            initial = compute_sha256(md)
            md.write_text("# original\n\nappended line\n", encoding="utf-8")
            current = compute_sha256(md)
            self.assertNotEqual(initial, current)
            out = Path(tmp) / "plan.comments.json"
            payload = {"comments": []}
            write_output_json(payload, out, md_file=str(md), md_sha256_initial=initial, md_sha256_current=current)
            written = json.loads(out.read_text())
            self.assertTrue(written["md_changed_during_review"])

    def test_ignores_client_supplied_md_file(self):
        """Server-supplied md_file must win; a spoofed payload cannot rename the file."""
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "a.comments.json"
            payload = {"md_file": "/etc/passwd", "comments": []}
            write_output_json(payload, out, md_file="/real/path.md", md_sha256_initial="x", md_sha256_current="x")
            written = json.loads(out.read_text())
            self.assertEqual(written["md_file"], "/real/path.md")


from scripts.serve import write_static_html


class StaticExportTests(unittest.TestCase):
    def test_writes_html_with_mode_static(self):
        with tempfile.TemporaryDirectory() as tmp:
            md = Path(tmp) / "a.md"
            md.write_text("# hello", encoding="utf-8")
            out = Path(tmp) / "a.review.html"
            write_static_html(md, out)
            html = out.read_text(encoding="utf-8")
            self.assertIn('window.__MODE__ = "static"', html)
            self.assertIn('"md_name": "a.md"', html)
            self.assertIn("<html", html.lower())


if __name__ == "__main__":
    unittest.main()
