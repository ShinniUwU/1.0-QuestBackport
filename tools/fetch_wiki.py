"""Fetch quest briefing text from the EFT fandom wiki into data/wiki.json.

usage: python fetch_wiki.py <data dir> <spt database dir>

Only quests SPT doesn't have are fetched; existing quests keep SPT's text.
"""
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import checks  # noqa: E402

DATA, SPT_DB = sys.argv[1], sys.argv[2]
checks.spt_database(SPT_DB)
checks.data_files(DATA, "tasks_pve.json")
API = "https://escapefromtarkov.fandom.com/api.php"
UA = "QuestBackport-builder/0.1 (SPT mod build script)"

tasks = json.load(open(f"{DATA}/tasks_pve.json", encoding="utf-8"))["data"]["tasks"]
tasks = tasks if isinstance(tasks, list) else list(tasks.values())
spt = json.load(open(f"{SPT_DB}/templates/quests.json", encoding="utf-8"))
try:
    cache = json.load(open(f"{DATA}/wiki.json", encoding="utf-8"))
except FileNotFoundError:
    cache = {}


def clean(s):
    s = re.sub(r"<br\s*/?>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", r"\1", s)
    s = re.sub(r"'''?", "", s)
    s = re.sub(r"\{\{[^{}]*\}\}", "", s)
    return re.sub(r"[ \t]+", " ", s).strip()


def quotes(text):
    """Contents of {{quote|...}}, allowing [[links]] inside."""
    out = []
    for m in re.finditer(r"\{\{\s*quote\s*\|", text, flags=re.I):
        depth, i = 2, m.end()
        while i < len(text) and depth:
            if text.startswith("{{", i):
                depth += 2
                i += 2
            elif text.startswith("}}", i):
                depth -= 2
                i += 2
            else:
                i += 1
        body = text[m.end():i - 2]
        out.append((m.start(), clean(body.split("|author=")[0])))
    return out


def section_pos(text, name):
    m = re.search(rf"^==\s*{name}\s*==", text, flags=re.M | re.I)
    return m.start() if m else -1


def parse(wikitext):
    q = quotes(wikitext)
    dlg, rew, guide = section_pos(wikitext, "Dialogue"), section_pos(wikitext, "Rewards"), section_pos(wikitext, "Guide")
    end = guide if guide > 0 else len(wikitext)
    desc = [t for p, t in q if dlg <= p < (rew if rew > 0 else end)]
    after = [t for p, t in q if rew > 0 and rew <= p < end]
    out = {}
    if desc:
        out["description"] = desc[0]
    if after:
        out["success"] = after[0]
    if len(desc) > 1:
        out["fail"] = desc[-1] if "fail" in wikitext[dlg:rew].lower() else None
    return {k: v for k, v in out.items() if v}


def fetch(page):
    qs = urllib.parse.urlencode({"action": "parse", "page": page, "prop": "wikitext", "format": "json", "redirects": 1})
    req = urllib.request.Request(f"{API}?{qs}", headers={"User-Agent": UA})
    d = json.load(urllib.request.urlopen(req, timeout=30))
    return d["parse"]["wikitext"]["*"] if "parse" in d else None


for t in tasks:
    if t["id"] in spt or t["id"] in cache or not t.get("wikiLink"):
        continue
    page = urllib.parse.unquote(t["wikiLink"].rsplit("/wiki/", 1)[-1])
    try:
        wt = fetch(page)
    except Exception as e:  # keep going; a missing page just keeps the placeholder
        print(f"  {page}: {e}")
        continue
    info = parse(wt) if wt else {}
    cache[t["id"]] = info
    print(f"  {page}: {', '.join(info) or 'no text found'}")
    time.sleep(0.5)

json.dump(cache, open(f"{DATA}/wiki.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print(f"wiki entries: {len(cache)}")
