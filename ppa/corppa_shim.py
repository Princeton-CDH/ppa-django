"""Compatibility shim for optional corppa dependency.

Commands and scripts that previously imported corppa should import this module
instead and call `get_corppa()` — it will return the real `corppa` module if
installed, or a shim that raises helpful errors when used.
"""
import importlib
import logging

logger = logging.getLogger(__name__)


def get_corppa():
    try:
        return importlib.import_module("corppa")
    except Exception:
        logger.warning(
            "corppa is not installed. Install the optional corppa dependency "
            "(see requirements.txt) to enable NLP/corpus utilities."
        )

        # Return a shim object that raises on attribute access
        class _Shim:
            def __getattr__(self, name):
                raise RuntimeError(
                    "Optional dependency 'corppa' is not installed. "
                    "Install it with `pip install -r requirements.txt`."
                )

        return _Shim()
