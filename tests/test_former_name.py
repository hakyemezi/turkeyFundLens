"""
The package was besfundlens until it took in securities investment funds. The
old name has to keep working for notebooks written against it, and has to give
back the same modules, not copies: the engine keeps its state in module
globals, and a second copy would be initialised separately.
"""

import importlib
import sys
import warnings

import turkeyfundlens


def fresh_import(name):
    for loaded in [m for m in sys.modules if m == "besfundlens" or m.startswith("besfundlens.")]:
        del sys.modules[loaded]
    return importlib.import_module(name)


def test_the_old_name_is_the_new_package():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        old = fresh_import("besfundlens")
    assert old is turkeyfundlens


def test_old_submodule_imports_give_the_same_modules():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        fresh_import("besfundlens")
        from besfundlens.core.engine import initialize_engine, safe_divide
        from besfundlens.core import engine as old_engine

    from turkeyfundlens.core import engine as new_engine

    assert old_engine is new_engine
    assert initialize_engine is new_engine.initialize_engine
    assert safe_divide(10, 4) == 2.5


def test_the_old_name_says_it_has_moved():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        fresh_import("besfundlens")
    assert any(
        issubclass(w.category, DeprecationWarning) and "turkeyfundlens" in str(w.message)
        for w in caught
    )
