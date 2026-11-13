"""Quest text translations, kept as spreadsheets so translators never touch JSON.

translations/en.csv is written by build.py: one row per piece of quest text,
with the id, the English text and an empty translation column. To add a
language, copy it to translations/<code>.csv using SPT's language code (see
LANGS), fill in the translation column in Excel, LibreOffice or Google Sheets,
and save it as CSV. Anything left empty shows up in English.

usage: python translations.py
    adds rows for new quest text to every translations/<code>.csv,
    keeping what's already translated
"""
import csv
import json
import os
import sys

DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "translations")
HEADER = ["id", "english", "translation"]
# the locale files SPT ships (SPT_Data/database/locales/global)
LANGS = {"ch", "cz", "es", "es-mx", "fr", "ge", "hu", "it", "jp", "kr", "pl", "po", "ro", "ru", "sk", "tu"}
# SPT language code -> the code tarkov.dev uses for the same language
LIVE = {"ch": "zh", "cz": "cs", "es": "es", "es-mx": "es", "fr": "fr", "ge": "de", "hu": "hu", "it": "it", "jp": "ja",
        "kr": "ko", "pl": "pl", "po": "pt", "ro": "ro", "ru": "ru", "sk": "sk", "tu": "tr"}


def _path(code):
    return os.path.join(DIR, f"{code}.csv")


def write_template(english):
    """english: {id: text}. Rewrites translations/en.csv."""
    os.makedirs(DIR, exist_ok=True)
    # utf-8-sig so Excel opens Cyrillic, Korean and Chinese text correctly
    with open(_path("en"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        for k in sorted(english):
            w.writerow([k, english[k], ""])


def read(code):
    """{id: translation} for the non-empty rows of translations/<code>.csv."""
    with open(_path(code), newline="", encoding="utf-8-sig") as f:
        text = f.read()
    # Excel saves with ";" in many European and Russian locales
    dialect = csv.Sniffer().sniff(text.split("\n", 1)[0], delimiters=",;\t")
    rows = csv.DictReader(text.splitlines(), dialect=dialect)
    return {r["id"]: r["translation"].strip() for r in rows if r.get("id") and (r.get("translation") or "").strip()}


def languages():
    """Language codes with a translations/<code>.csv, warning about codes SPT doesn't have."""
    if not os.path.isdir(DIR):
        return []
    codes = sorted(f[:-4] for f in os.listdir(DIR) if f.endswith(".csv") and f != "en.csv")
    for c in codes:
        if c not in LANGS:
            print(f"warning: translations/{c}.csv isn't an SPT language code ({', '.join(sorted(LANGS))})")
    return [c for c in codes if c in LANGS]


def live(data_dir, code, live_en):
    """{id: text} of tarkov.dev's 1.0 quest text in that language (data/tasks_pve_<code>.json,
    from fetch_data.py), without the strings tarkov.dev itself still has in English."""
    path = os.path.join(data_dir, f"tasks_pve_{LIVE.get(code)}.json")
    if code not in LIVE or not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)["data"]
    return {k: v for k, v in data.items() if isinstance(v, str) and v and v != live_en.get(k)}


def localize(english, translated, native=None, native_en=None, live=None, live_en=None):
    """Text for one language. Every key gets a value so nothing shows up as a raw id:
    the translator's text, else the 1.0 game's own translation when our English is still
    the 1.0 English (not a stand-in we reworded), else SPT's own text in that language
    when 1.0 didn't change the English (quests we only patched), else English."""
    native, native_en = native or {}, native_en or {}
    live, live_en = live or {}, live_en or {}
    out = {}
    for k, v in english.items():
        if translated.get(k):
            out[k] = translated[k]
        elif live.get(k) and live_en.get(k) == v:
            out[k] = live[k]
        elif k in native and native.get(k) and native_en.get(k) == v:
            out[k] = native[k]
        else:
            out[k] = v
    return out


def refresh():
    with open(_path("en"), newline="", encoding="utf-8-sig") as f:
        english = {r["id"]: r["english"] for r in csv.DictReader(f)}
    for code in languages():
        done = read(code)
        with open(_path(code), "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(HEADER)
            for k in sorted(english):
                w.writerow([k, english[k], done.get(k, "")])
        print(f"{code}: {sum(1 for k in english if k in done)}/{len(english)} translated")


if __name__ == "__main__":
    if not os.path.exists(_path("en")):
        sys.exit("translations/en.csv doesn't exist yet, run a build first")
    refresh()
