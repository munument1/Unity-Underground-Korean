#!/usr/bin/env python3
"""Refine v1.1.0 global-map application without changing the base plugin."""
from pathlib import Path

path = Path("tools/apply_completed_retranslations.py")
text = path.read_text(encoding="utf-8")
old = '''    return (\n        source in DYNAMIC_SOURCES\n        or "%s" in source\n        or "{0}" in source\n        or source != source.strip()\n    )\n'''
new = '''    return (\n        source in DYNAMIC_SOURCES\n        or "%s" in source\n        or "{0}" in source\n    )\n'''
if old in text:
    text = text.replace(old, new, 1)
elif new not in text:
    raise SystemExit("dynamic source rule not found")

anchor = '    "You have attained experience level ", " tasted putrid.",\n'
replacement = (
    '    "You have attained experience level ", "Restoring Game ", "Saving Game ",\n'
    '    " tasted putrid.",\n'
)
if '"Restoring Game "' not in text:
    if anchor not in text:
        raise SystemExit("save/load source insertion anchor not found")
    text = text.replace(anchor, replacement, 1)

path.write_text(text, encoding="utf-8")
print("v1.1.0 global-map rules refined")
