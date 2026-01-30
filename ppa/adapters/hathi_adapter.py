"""Hathi adapter shim module.

This module provides an adapter interface for Hathi-specific logic. Deployments
can replace or extend this adapter in `ARCHIVE_ADAPTER` if desired.
"""
import logging
from ppa.flags import is_flag_enabled

logger = logging.getLogger(__name__)

if is_flag_enabled("ENABLE_HATHI"):
    # import real implementations from existing module
    from ppa.archive.hathi import HathiBibliographicAPI, HathiObject, HathiItemNotFound
else:
    # provide lightweight stubs that raise helpful errors when used
    class HathiBibliographicAPI:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("Hathi adapter is disabled (ENABLE_HATHI=False)")

    class HathiObject:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("Hathi adapter is disabled (ENABLE_HATHI=False)")

    class HathiItemNotFound(Exception):
        pass
