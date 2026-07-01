import hashlib
import unittest
from pathlib import Path

from scripts.serve import compute_sha256


class ComputeSha256Tests(unittest.TestCase):
    def test_matches_stdlib_hash(self):
        fixture = Path(__file__).parent / "fixtures" / "sample.md"
        expected = hashlib.sha256(fixture.read_bytes()).hexdigest()
        self.assertEqual(compute_sha256(fixture), expected)


if __name__ == "__main__":
    unittest.main()
