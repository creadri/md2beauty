"""
Compatibility shim for md2beauty.converters

Converters moved to the md2beauty/converters/ package as separate modules.
Import from md2beauty.converters (package) instead of md2beauty.converters.py.
"""

# Re-export everything from the new package for backward compatibility
from .converters import *  # type: ignore  # noqa: F401,F403
