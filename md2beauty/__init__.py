"""md2beauty package init.

Provides a small helper to toggle debug behavior across the library via
an environment variable or CLI flag.
"""

from __future__ import annotations

import os


def is_debug() -> bool:
	"""Return True if debug mode is enabled.

	Controlled by environment variable MD2BEAUTY_DEBUG in {1,true,yes,on} (case-insensitive).
	"""
	return os.getenv("MD2BEAUTY_DEBUG", "").strip().lower() in ("1", "true", "yes", "on")

