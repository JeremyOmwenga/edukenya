"""
Compile every locale/*/LC_MESSAGES/*.po into .mo files.

Django's `compilemessages` needs GNU gettext, which Windows does not ship.
This does the same job with polib. Run from the project root:

    python scripts/compile_messages.py
"""
from pathlib import Path

import polib

ROOT = Path(__file__).resolve().parent.parent

po_files = sorted((ROOT / "locale").glob("*/LC_MESSAGES/*.po"))
if not po_files:
    raise SystemExit("No .po files found under locale/")

for po_path in po_files:
    po = polib.pofile(str(po_path))
    mo_path = po_path.with_suffix(".mo")
    po.save_as_mofile(str(mo_path))
    untranslated = len(po.untranslated_entries())
    print(f"{po_path.relative_to(ROOT)} -> {mo_path.name} "
          f"({len(po.translated_entries())} translated, {untranslated} untranslated)")
