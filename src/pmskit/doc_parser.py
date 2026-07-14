# -*- coding: utf-8 -*-
"""Low-level extraction of text from a Word-binary (.doc) OLE file.

Reads the ``WordDocument`` stream piece table directly, so it is fast and needs
no Microsoft Word or LibreOffice. Table cells are 0x07-delimited, paragraphs
0x0D. This module is format-agnostic; company-specific structure lives in
:mod:`pmskit.adapters`.
"""
from __future__ import annotations
import struct

try:
    import olefile
except ImportError:  # pragma: no cover
    olefile = None


def extract_text(path: str) -> str:
    """Return the full document text (with 0x07 cell / 0x0D paragraph marks)."""
    if olefile is None:
        raise RuntimeError("olefile is required to read .doc files: pip install olefile")
    ole = olefile.OleFileIO(path)
    wd = ole.openstream("WordDocument").read()
    flags = struct.unpack_from("<H", wd, 0x0A)[0]
    table_stream = "1Table" if (flags >> 9) & 1 else "0Table"
    fc_clx, lcb_clx = struct.unpack_from("<ii", wd, 0x01A2)
    clx = ole.openstream(table_stream).read()[fc_clx:fc_clx + lcb_clx]

    # Walk the CLX to find the piece table (Pcdt, type byte 0x02).
    i, pcdt = 0, None
    while i < len(clx):
        if clx[i] == 2:
            lcb = struct.unpack_from("<I", clx, i + 1)[0]
            pcdt = clx[i + 5:i + 5 + lcb]
            break
        elif clx[i] == 1:
            i += 3 + struct.unpack_from("<H", clx, i + 1)[0]
        else:
            i += 1
    if pcdt is None:
        raise ValueError("No piece table found; unsupported .doc variant")

    n = (len(pcdt) - 4) // 12
    cps = [struct.unpack_from("<I", pcdt, k * 4)[0] for k in range(n + 1)]
    off = (n + 1) * 4
    out = []
    for k in range(n):
        fcval = struct.unpack_from("<I", pcdt, off + k * 8 + 2)[0]
        clen = cps[k + 1] - cps[k]
        fc = fcval & 0x3FFFFFFF
        if (fcval >> 30) & 1:              # 1-byte (ANSI/cp1256) piece
            fc //= 2
            out.append(wd[fc:fc + clen].decode("cp1256", "replace"))
        else:                              # 2-byte (UTF-16LE) piece
            out.append(wd[fc:fc + clen * 2].decode("utf-16-le", "replace"))
    return "".join(out)
