from __future__ import annotations

import re


_XML_DECL_RE = re.compile(r"^\s*<\?xml[^>]*>\s*", re.IGNORECASE)


def optimize_svg(svg_text: str | None) -> str | None:
    if svg_text is None:
        return None
    text = str(svg_text).strip()
    if not text:
        return None
    text = _XML_DECL_RE.sub("", text)
    text = re.sub(r">\s+<", "><", text)
    return text.strip()
