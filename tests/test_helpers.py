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


if __name__ == "__main__":
    unittest.main()
