"""Download the tarkov.dev data the build needs and index WTT-ContentBackport's items.

usage: python fetch_data.py <data dir> <SPT_Runtime dir>

tarkov.dev's GraphQL API is not used; json.tarkov.dev serves the same data as
static files and stays up when the API is down.
"""
import json
import os
import re
import sys
import urllib.request

DATA, SPT = sys.argv[1], sys.argv[2]
BASE = "https://json.tarkov.dev"
FILES = {
    "tasks_pve.json": "pve/tasks",
    "tasks_pve_en.json": "pve/tasks_en",
    "items.json": "regular/items",
    "items_en.json": "regular/items_en",
    "traders.json": "regular/traders",
}
UA = "shinnis-questsbackport-build/0.1"

os.makedirs(DATA, exist_ok=True)
for name, path in FILES.items():
    req = urllib.request.Request(f"{BASE}/{path}", headers={"User-Agent": UA})
    body = urllib.request.urlopen(req, timeout=120).read()
    json.loads(body)  # fail loudly on a truncated download
    open(os.path.join(DATA, name), "wb").write(body)
    print(f"  {name}: {len(body) // 1024} KB")

# Item ids WTT-ContentBackport adds at runtime. SPT's items.json doesn't have
# them, but quests may use them as long as that mod is installed.
wtt = os.path.join(SPT, "user", "mods", "WTT-ContentBackport", "db")
ids = set()
for root, _, files in os.walk(wtt):
    for f in files:
        if f.endswith((".json", ".jsonc")):
            txt = open(os.path.join(root, f), encoding="utf-8-sig").read()
            ids |= set(re.findall(r'"([0-9a-f]{24})"\s*:', txt))
            ids |= set(re.findall(r'"(?:id|_id|newId|ItemId)"\s*:\s*"([0-9a-f]{24})"', txt, flags=re.I))
json.dump(sorted(ids), open(os.path.join(DATA, "wtt_ids.json"), "w"))
print(f"  wtt_ids.json: {len(ids)} ids from {wtt}")
