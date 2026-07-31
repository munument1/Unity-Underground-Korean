#!/usr/bin/env python3
"""Add verified runtime-composed save/load prefixes to the application audit."""
from pathlib import Path

path = Path("tools/apply_completed_retranslations.py")
text = path.read_text(encoding="utf-8")
anchor = '    "You have attained experience level ", " tasted putrid.",\n'
replacement = (
    '    "You have attained experience level ", "Restoring Game ", "Saving Game ",\n'
    '    " tasted putrid.",\n'
)
if '"Restoring Game "' not in text:
    if anchor not in text:
        raise SystemExit("dynamic source insertion anchor not found")
    text = text.replace(anchor, replacement, 1)
    path.write_text(text, encoding="utf-8")
print("save/load dynamic sources ready")
