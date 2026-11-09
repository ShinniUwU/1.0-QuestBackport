"""Convert objectives of quests SPT already has and diff against SPT's real JSON.

Mismatches that repeat across many quests point at converter bugs.
One-off mismatches are usually real 1.0 changes.
"""
import json
import sys
from collections import Counter, defaultdict

import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from convert import Ctx, convert_objective  # noqa: E402

DATA, SPT_DB = sys.argv[1], sys.argv[2]
ctx = Ctx(SPT_DB, json.load(open(f"{DATA}/wtt_ids.json")))
ctx.text = {k: v for k, v in json.load(open(f"{DATA}/tasks_pve_en.json", encoding="utf-8"))["data"].items()}
tasks = json.load(open(f"{DATA}/tasks_pve.json", encoding="utf-8"))["data"]["tasks"]
tasks = tasks if isinstance(tasks, list) else list(tasks.values())

spt_conds = {}
for q in ctx.quests.values():
    for c in q["conditions"]["AvailableForFinish"]:
        spt_conds[c["id"]] = c


def sig(c):
    """Fields that must match for the condition to behave the same."""
    if c is None:
        return None
    s = {"ct": c["conditionType"], "type": c.get("type")}
    for k in ("target", "zoneId", "onlyFoundInRaid", "dogtagLevel", "status"):
        if k in c:
            v = c[k]
            s[k] = sorted(v) if isinstance(v, list) and all(isinstance(x, (str, int)) for x in v) else v
    subs = []
    for sc in (c.get("counter") or {}).get("conditions", []):
        d = {"ct": sc["conditionType"]}
        for k in ("target", "savageRole", "bodyPart", "zoneIds", "status", "exitName", "distance", "daytime"):
            if k in sc:
                v = sc[k]
                d[k] = sorted(v) if isinstance(v, list) and all(isinstance(x, str) for x in v) else v
        subs.append(json.dumps(d, sort_keys=True))
    if subs:
        s["subs"] = sorted(subs)
    return s


total = Counter()
bad = Counter()
field_bad = defaultdict(Counter)
examples = defaultdict(list)
for t in tasks:
    if t["id"] not in ctx.quests:
        continue
    for i, o in enumerate(t["objectives"]):
        if o["id"] not in spt_conds:
            continue
        mine = convert_objective(o, t["id"], ctx, i)
        a, b = sig(mine), sig(spt_conds[o["id"]])
        total[o["type"]] += 1
        if a != b:
            bad[o["type"]] += 1
            for k in set(a or {}) | set(b or {}):
                if (a or {}).get(k) != (b or {}).get(k):
                    field_bad[o["type"]][k] += 1
                    if len(examples[(o["type"], k)]) < 2:
                        examples[(o["type"], k)].append((t["id"], o["id"], (a or {}).get(k), (b or {}).get(k)))

for typ in sorted(total, key=lambda x: -total[x]):
    print(f"{typ:15} {total[typ]:4} converted, {bad[typ]:4} differ  fields: {dict(field_bad[typ])}")
print()
for (typ, k), exs in sorted(examples.items()):
    for qid, oid, mine, theirs in exs:
        m, th = json.dumps(mine)[:300], json.dumps(theirs)[:300]
        print(f"[{typ}.{k}] {qid}/{oid}\n   mine:   {m}\n   spt:    {th}")
