# -*- coding: utf-8 -*-
"""Registry of PMS layout adapters."""
from __future__ import annotations
from .base import PMSAdapter
from .nioec import NIOECAdapter

_ADAPTERS = {a.name: a for a in [NIOECAdapter]}


def list_adapters():
    return {name: cls.label for name, cls in _ADAPTERS.items()}


def get_adapter(name: str) -> PMSAdapter:
    name = (name or "nioec").lower()
    if name not in _ADAPTERS:
        raise KeyError(f"Unknown adapter '{name}'. Available: {', '.join(_ADAPTERS)}")
    return _ADAPTERS[name]()
