# Copyright (c) 2026 Jeroen Visser. All rights reserved.
# Licensed under the MIT License — see LICENSE.
"""Package version via installed metadata.

Single source of truth: pyproject.toml → installed metadata → this module.
"""
from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("humeris-core")
except PackageNotFoundError:
    __version__ = "0.0.0"
