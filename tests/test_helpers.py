import hashlib
import unittest
from pathlib import Path

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
            result = find_free_port(busy_port, next_free)
            self.assertNotEqual(result, busy_port)
            self.assertTrue(busy_port <= result <= next_free)

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


if __name__ == "__main__":
    unittest.main()
