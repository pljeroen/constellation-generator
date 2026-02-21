# Copyright (c) 2026 Jeroen Visser. All rights reserved.
# Licensed under the MIT License — see LICENSE.
"""Tests for humeris.version module."""
import unittest


class TestVersion(unittest.TestCase):
    """Verify version module reads from installed metadata."""

    def test_version_is_string(self):
        from humeris.version import __version__
        self.assertIsInstance(__version__, str)

    def test_version_not_fallback(self):
        """Installed package should have a real version, not the fallback."""
        from humeris.version import __version__
        self.assertNotEqual(__version__, "0.0.0")

    def test_version_matches_pyproject(self):
        """Version must match what pyproject.toml declares."""
        from humeris.version import __version__
        import importlib.metadata
        expected = importlib.metadata.version("humeris-core")
        self.assertEqual(__version__, expected)

    def test_version_semver_format(self):
        """Version should be a valid semver-like string."""
        from humeris.version import __version__
        parts = __version__.split(".")
        self.assertGreaterEqual(len(parts), 2)
        for part in parts:
            self.assertTrue(part.isdigit(), f"Non-numeric version part: {part}")


if __name__ == "__main__":
    unittest.main()
