# -*- coding: utf-8 -*-
"""Adapter interface for company-specific PMS layouts.

A PMS from each owner/EPC is laid out differently. An adapter knows how to turn
one company's document into the canonical schema (see ``schema/pms.schema.json``).
Add support for a new company by subclassing :class:`PMSAdapter` and registering
it in ``adapters/__init__.py`` — this is the intended "import" extension point.
"""
from __future__ import annotations
from typing import List, Dict, Any


class PMSAdapter:
    #: short identifier, e.g. "nioec"
    name: str = "base"
    #: human label
    label: str = "Base adapter"

    def parse(self, path: str, company: str | None = None) -> Dict[str, Any]:
        """Parse ``path`` into a canonical PMS dict: ``{"meta": {...}, "classes": [...]}``."""
        raise NotImplementedError

    # -- helpers shared by adapters --------------------------------------
    @staticmethod
    def envelope(classes: List[dict], company: str, source_file: str) -> Dict[str, Any]:
        return {
            "meta": {
                "source_file": source_file,
                "company": company,
                "class_count": len(classes),
                "generator": "pms-toolkit",
                "units": {"temperature": "C", "pressure": "barg", "size": "NPS (inch)"},
            },
            "classes": classes,
        }
