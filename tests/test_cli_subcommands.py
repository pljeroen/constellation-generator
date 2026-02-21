# Copyright (c) 2026 Jeroen Visser. All rights reserved.
# Licensed under the MIT License — see LICENSE.
"""Tests for CLI subcommand structure and backward compatibility."""
import subprocess
import sys
import unittest


class TestCliVersion(unittest.TestCase):
    """humeris --version prints version and exits."""

    def test_version_flag(self):
        result = subprocess.run(
            [sys.executable, "-m", "humeris.cli", "--version"],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("humeris-core", result.stdout)

    def test_version_is_semver(self):
        result = subprocess.run(
            [sys.executable, "-m", "humeris.cli", "--version"],
            capture_output=True, text=True, timeout=10,
        )
        version_str = result.stdout.strip().split()[-1]
        parts = version_str.split(".")
        self.assertGreaterEqual(len(parts), 2)


class TestCliSubcommandHelp(unittest.TestCase):
    """Each subcommand has --help."""

    def test_serve_help(self):
        result = subprocess.run(
            [sys.executable, "-m", "humeris.cli", "serve", "--help"],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("--port", result.stdout)
        self.assertIn("--load-session", result.stdout)
        self.assertIn("--headless", result.stdout)

    def test_generate_help(self):
        result = subprocess.run(
            [sys.executable, "-m", "humeris.cli", "generate", "--help"],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("--input", result.stdout)
        self.assertIn("--output", result.stdout)
        self.assertIn("--export-csv", result.stdout)
        self.assertIn("--live-group", result.stdout)

    def test_import_help(self):
        result = subprocess.run(
            [sys.executable, "-m", "humeris.cli", "import", "--help"],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("opm", result.stdout)
        self.assertIn("oem", result.stdout)

    def test_import_opm_help(self):
        result = subprocess.run(
            [sys.executable, "-m", "humeris.cli", "import", "opm", "--help"],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("file", result.stdout)

    def test_sweep_help(self):
        result = subprocess.run(
            [sys.executable, "-m", "humeris.cli", "sweep", "--help"],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("--param", result.stdout)
        self.assertIn("--metric", result.stdout)

    def test_root_help_shows_subcommands(self):
        result = subprocess.run(
            [sys.executable, "-m", "humeris.cli", "--help"],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0)
        for cmd in ("serve", "generate", "import", "sweep"):
            self.assertIn(cmd, result.stdout)


class TestCliLegacyDeprecation(unittest.TestCase):
    """Old-style flags work but emit deprecation warnings."""

    def test_legacy_serve_emits_warning(self):
        """--serve still works but prints deprecation."""
        script = (
            "import sys\n"
            "sys.argv = ['humeris', '--serve']\n"
            "from unittest.mock import patch\n"
            "with patch('humeris.cli._run_serve'):\n"
            "    from humeris.cli import main\n"
            "    main()\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("DeprecationWarning", result.stderr)
        self.assertIn("humeris serve", result.stderr)

    def test_legacy_import_opm_emits_warning(self, tmp_path=None):
        """--import-opm still works but prints deprecation."""
        import tempfile
        import os
        from humeris.domain.ccsds_parser import parse_opm
        opm_text = (
            "CCSDS_OPM_VERS = 2.0\n"
            "CREATION_DATE = 2026-01-01T00:00:00\n"
            "ORIGINATOR = TEST\n"
            "OBJECT_NAME = TESTSAT\n"
            "OBJECT_ID = 2026-001A\n"
            "CENTER_NAME = EARTH\n"
            "REF_FRAME = EME2000\n"
            "TIME_SYSTEM = UTC\n"
            "EPOCH = 2026-01-01T12:00:00.000\n"
            "X = 6678.137\nY = 0.0\nZ = 0.0\n"
            "X_DOT = 0.0\nY_DOT = 7.725\nZ_DOT = 0.0\n"
        )
        fd, path = tempfile.mkstemp(suffix=".opm")
        try:
            os.write(fd, opm_text.encode())
            os.close(fd)
            result = subprocess.run(
                [sys.executable, "-m", "humeris.cli", "--import-opm", path],
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
            self.assertIn("TESTSAT", result.stdout)
            self.assertIn("DeprecationWarning", result.stderr)
            self.assertIn("humeris import opm", result.stderr)
        finally:
            os.unlink(path)

    def test_legacy_bare_generate_emits_warning(self):
        """humeris -i ... -o ... still works but prints deprecation."""
        script = (
            "import sys\n"
            "sys.argv = ['humeris', '-i', 'fake.json', '-o', 'out.json']\n"
            "from unittest.mock import patch\n"
            "from humeris.cli import main\n"
            "try:\n"
            "    main()\n"
            "except SystemExit:\n"
            "    pass\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True, timeout=10,
        )
        self.assertIn("DeprecationWarning", result.stderr)
        self.assertIn("humeris generate", result.stderr)


class TestCliNewSyntax(unittest.TestCase):
    """New subcommand syntax works."""

    def test_serve_subcommand(self):
        """'humeris serve' invokes serve."""
        script = (
            "import sys\n"
            "sys.argv = ['humeris', 'serve']\n"
            "from unittest.mock import patch\n"
            "with patch('humeris.cli._run_serve'):\n"
            "    from humeris.cli import main\n"
            "    main()\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0)
        # No deprecation warning for new syntax
        self.assertNotIn("DeprecationWarning", result.stderr)

    def test_import_opm_subcommand(self):
        """'humeris import opm FILE' works."""
        import tempfile
        import os
        opm_text = (
            "CCSDS_OPM_VERS = 2.0\n"
            "CREATION_DATE = 2026-01-01T00:00:00\n"
            "ORIGINATOR = TEST\n"
            "OBJECT_NAME = TESTSAT2\n"
            "OBJECT_ID = 2026-002A\n"
            "CENTER_NAME = EARTH\n"
            "REF_FRAME = EME2000\n"
            "TIME_SYSTEM = UTC\n"
            "EPOCH = 2026-01-01T12:00:00.000\n"
            "X = 6678.137\nY = 0.0\nZ = 0.0\n"
            "X_DOT = 0.0\nY_DOT = 7.725\nZ_DOT = 0.0\n"
        )
        fd, path = tempfile.mkstemp(suffix=".opm")
        try:
            os.write(fd, opm_text.encode())
            os.close(fd)
            result = subprocess.run(
                [sys.executable, "-m", "humeris.cli", "import", "opm", path],
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
            self.assertIn("TESTSAT2", result.stdout)
            self.assertNotIn("DeprecationWarning", result.stderr)
        finally:
            os.unlink(path)


class TestRewriteLegacyArgv(unittest.TestCase):
    """Unit tests for _rewrite_legacy_argv."""

    def test_serve_rewrite(self):
        from humeris.cli import _rewrite_legacy_argv
        argv, warnings = _rewrite_legacy_argv(
            ['humeris', '--serve', '--port', '9000']
        )
        self.assertEqual(argv, ['humeris', 'serve', '--port', '9000'])
        self.assertEqual(len(warnings), 1)

    def test_import_opm_rewrite(self):
        from humeris.cli import _rewrite_legacy_argv
        argv, warnings = _rewrite_legacy_argv(
            ['humeris', '--import-opm', '/path/to/file.opm']
        )
        self.assertEqual(argv, ['humeris', 'import', 'opm', '/path/to/file.opm'])
        self.assertEqual(len(warnings), 1)

    def test_import_oem_rewrite(self):
        from humeris.cli import _rewrite_legacy_argv
        argv, warnings = _rewrite_legacy_argv(
            ['humeris', '--import-oem', '/path/to/file.oem']
        )
        self.assertEqual(argv, ['humeris', 'import', 'oem', '/path/to/file.oem'])
        self.assertEqual(len(warnings), 1)

    def test_bare_generate_rewrite(self):
        from humeris.cli import _rewrite_legacy_argv
        argv, warnings = _rewrite_legacy_argv(
            ['humeris', '-i', 'in.json', '-o', 'out.json', '--export-csv', 'x.csv']
        )
        self.assertEqual(
            argv,
            ['humeris', 'generate', '-i', 'in.json', '-o', 'out.json', '--export-csv', 'x.csv'],
        )
        self.assertEqual(len(warnings), 1)

    def test_new_syntax_no_rewrite(self):
        from humeris.cli import _rewrite_legacy_argv
        argv, warnings = _rewrite_legacy_argv(
            ['humeris', 'serve', '--port', '8080']
        )
        self.assertEqual(argv, ['humeris', 'serve', '--port', '8080'])
        self.assertEqual(len(warnings), 0)

    def test_empty_argv_no_rewrite(self):
        from humeris.cli import _rewrite_legacy_argv
        argv, warnings = _rewrite_legacy_argv(['humeris'])
        self.assertEqual(argv, ['humeris'])
        self.assertEqual(len(warnings), 0)


if __name__ == "__main__":
    unittest.main()
