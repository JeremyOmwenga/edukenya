"""
Extract translatable strings into locale/<lang>/LC_MESSAGES/django.po without
GNU gettext (which Windows lacks). Existing translations are kept; new strings
are added with an empty msgstr; strings no longer used are marked obsolete.

    python scripts/make_messages.py            # update .po files
    python scripts/make_messages.py --check    # exit 1 if anything is untranslated (CI)

Templates are converted with Django's own templatize() (the same step
makemessages uses), then Python's tokenizer picks out gettext calls.
"""
import argparse
import ast
import io
import os
import sys
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "edukenya.settings")

import django  # noqa: E402

django.setup()

import polib  # noqa: E402
from django.utils.translation.template import templatize  # noqa: E402

FUNCS = {"gettext", "gettext_lazy", "_", "gettext_noop", "pgettext", "pgettext_lazy",
         "ngettext", "ngettext_lazy"}
SKIP_DIRS = {".venv", "node_modules", "staticfiles", ".git", "tests", "scripts", "migrations"}
# The console is for the platform owner only and stays English.
SKIP_PARTS = {("console", "templates")}


def iter_files():
    for path in ROOT.rglob("*"):
        rel = path.relative_to(ROOT)
        if any(p in SKIP_DIRS for p in rel.parts):
            continue
        if any(rel.parts[i:i + 2] == pair for pair in SKIP_PARTS for i in range(len(rel.parts))):
            continue
        if path.suffix in {".html", ".txt"} and "templates" in rel.parts:
            yield path, "template"
        elif path.suffix == ".py":
            yield path, "python"


def calls_in_python(source):
    """Yield (func, args) for gettext-like calls whose args are string literals."""
    tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    for i, tok in enumerate(tokens):
        if tok.type != tokenize.NAME or tok.string not in FUNCS:
            continue
        if i + 1 >= len(tokens) or tokens[i + 1].string != "(":
            continue
        args, j, cur = [], i + 2, []
        depth = 1
        while j < len(tokens) and depth:
            t = tokens[j]
            if t.string in "([{":
                depth += 1
            elif t.string in ")]}":
                depth -= 1
            if depth == 1 and t.string == ",":
                args.append(cur)
                cur = []
            elif depth >= 1:
                cur.append(t)
            j += 1
        args.append(cur)
        literals = []
        for a in args:
            strings = [t for t in a if t.type == tokenize.STRING]
            others = [t for t in a if t.type not in (tokenize.STRING, tokenize.NL, tokenize.NEWLINE, tokenize.COMMENT)]
            if strings and not others:
                literals.append("".join(ast.literal_eval(t.string) for t in strings))
            else:
                literals.append(None)
        yield tok.string, literals


def extract():
    found = {}  # (msgctxt, msgid) -> (msgid_plural, [locations])
    for path, kind in iter_files():
        text = path.read_text(encoding="utf-8")
        if kind == "template":
            if "{%" not in text:
                continue
            source = templatize(text, origin=str(path))
        else:
            source = text
        rel = path.relative_to(ROOT).as_posix()
        for func, lits in calls_in_python(source):
            if func.startswith("pgettext"):
                ctx, msgid, plural = (lits + [None, None])[0], (lits + [None, None])[1], None
            elif func.startswith("ngettext"):
                ctx, msgid, plural = None, lits[0], (lits[1] if len(lits) > 1 else None)
            else:
                ctx, msgid, plural = None, lits[0] if lits else None, None
            if not msgid:
                continue
            entry = found.setdefault((ctx, msgid), [plural, []])
            if rel not in entry[1]:
                entry[1].append(rel)
    return found


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    found = extract()
    exit_code = 0
    for po_path in sorted((ROOT / "locale").glob("*/LC_MESSAGES/django.po")):
        po = polib.pofile(str(po_path), wrapwidth=79)
        existing = {(e.msgctxt, e.msgid): e for e in po if not e.obsolete}
        added = 0
        for (ctx, msgid), (plural, locs) in found.items():
            entry = existing.get((ctx, msgid))
            if entry is None:
                entry = polib.POEntry(msgid=msgid, msgstr="", msgctxt=ctx)
                if plural:
                    entry.msgid_plural = plural
                    entry.msgstr_plural = {0: "", 1: ""}
                po.append(entry)
                added += 1
            entry.occurrences = [(loc, "") for loc in sorted(locs)]
        obsolete = 0
        for key, entry in existing.items():
            if key not in found and key[1] not in {"English", "Kiswahili"}:
                entry.obsolete = True
                obsolete += 1
        missing = [e.msgid for e in po if not e.obsolete and not e.translated()]
        if args.check:
            if added or missing:
                print(f"{po_path.relative_to(ROOT)}: {added} new, {len(missing)} untranslated")
                for m in missing[:20]:
                    print("   -", m[:90])
                exit_code = 1
        else:
            po.save(str(po_path))
            print(f"{po_path.relative_to(ROOT)}: {added} added, {obsolete} obsolete, {len(missing)} untranslated")
            for m in missing:
                print("   -", m)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
