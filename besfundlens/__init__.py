"""
besfundlens is now turkeyfundlens.

The package was renamed in October 2026, when securities investment funds
joined the pension (BES) funds it started with. This keeps the old name
importing the same modules — ``from besfundlens.core.engine import safe_divide``
included — so existing notebooks and scripts keep working, with a warning to
move to the new name.
"""

import importlib
import pkgutil
import sys
import warnings

import turkeyfundlens

warnings.warn(
    "besfundlens has been renamed turkeyfundlens; import turkeyfundlens instead.",
    DeprecationWarning,
    stacklevel=2,
)

# Every module under the new name is registered under the old one as well, so a
# submodule import finds the very same module object rather than loading a
# second copy with state of its own: the engine keeps its panel in module
# globals, and two copies would not see each other's.
for _info in pkgutil.walk_packages(turkeyfundlens.__path__, prefix="turkeyfundlens."):
    _module = importlib.import_module(_info.name)
    sys.modules["besfundlens" + _info.name[len("turkeyfundlens"):]] = _module

sys.modules[__name__] = turkeyfundlens
