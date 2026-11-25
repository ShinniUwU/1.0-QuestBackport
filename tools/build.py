"""Build QuestBackport's db folder from tarkov.dev data.

usage: python build.py <data dir> <spt database dir> <output mod dir>

New 1.0 quests are generated in full. Quests SPT already has are patched in
place (counts, levels, targets, rewards) so condition ids, and with them
existing profile progress, stay valid.
"""
import copy
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from convert import (MAP_SUBSTITUTES, STATUS, Ctx, _equipment_sub, _location_sub, _zone_ids,  # noqa: E402
                     convert_objective, mongo_id, wearing_groups)
import translations  # noqa: E402
import checks  # noqa: E402

DATA, SPT_DB, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
checks.spt_database(SPT_DB)
checks.data_files(DATA, "wtt_ids.json", "tasks_pve.json", "tasks_pve_en.json")
ROUBLES, DOLLARS, EUROS, GP = "5449016a4bdc2d6f028b456f", "5696686a4bdc2da3298b456a", "569668774bdc2da2298b4568", "5d235b4d86f7742e017bc88a"
MONEY = {ROUBLES, DOLLARS, EUROS, GP}

# Prestige quests run through SPT's prestige system, not trader quest lists.
SKIP = {
    "6761f28a022f60bb320f3e95", "6761ff17cdc36bd66102e9d0",
    "6848100b00afffa81f09e365", "68481881f43abfdda2058369",
}

ctx = Ctx(SPT_DB, json.load(open(f"{DATA}/wtt_ids.json")))
TEXT = json.load(open(f"{DATA}/tasks_pve_en.json", encoding="utf-8"))["data"]
ctx.text = TEXT
WIKI = json.load(open(f"{DATA}/wiki.json", encoding="utf-8")) if os.path.exists(f"{DATA}/wiki.json") else {}
OVERRIDES = json.load(open(os.path.join(os.path.dirname(__file__), "overrides.json"), encoding="utf-8"))
# SPT mirrors live PvE (it ships the "PVE ZONE" Ref quests), so use the PvE task list.
tasks = json.load(open(f"{DATA}/tasks_pve.json", encoding="utf-8"))["data"]["tasks"]
tasks = tasks if isinstance(tasks, list) else list(tasks.values())
TASK_IDS = {t["id"] for t in tasks}
# 1.0 unlocks many quests once N quests are done for a trader at a loyalty level. Each trader has one
# counter per level, and their ids sort LL1..LL4 (this matches the wiki of every new quest that has one).
_counters = {}
for _t in tasks:
    for _r in _t.get("otherRequirements") or []:
        if _r.get("type") == "globalVariable":
            _counters.setdefault(_t["trader"], set()).add(_r["variableId"])
COUNTER_LL = {v: i + 1 for vs in _counters.values() for i, v in enumerate(sorted(vs))}
QUEST_LOCKS = {}  # quest -> {trader, level, count}; Mod.cs hides the quest until that many are done

# RefFriendlyQuests (acidphantasm) rewrites these Ref quests at PostLoad + 14, after us.
# Leave them alone so its versions are the ones players get.
REF_FRIENDLY = {
    "68341eb25619c8e2a9031501", "68341f6fe2e7ef70a3060a0a", "6834202a186efa3c5b07f9a2",
    "683421515619c8e2a9031511", "68342265a8d674b5740b31f0", "68342446a8d674b5740b31fc",
}
_rfq = os.path.join(SPT_DB, "..", "..", "user", "mods", "acidphantasm-reffriendlyquests", "db", "quests.json")
if os.path.exists(_rfq):
    REF_FRIENDLY |= set(json.load(open(_rfq, encoding="utf-8-sig")))
_td_traders = json.load(open(f"{DATA}/traders.json", encoding="utf-8"))["data"]
_td_traders = _td_traders.get("traders", _td_traders)
_td_traders = _td_traders if isinstance(_td_traders, list) else list(_td_traders.values())
STANDING_RATIO = {}
for _t in _td_traders:
    _p = f"{SPT_DB}/traders/{_t['id']}/base.json"
    if os.path.exists(_p) and _t.get("levels"):
        _spt_max = json.load(open(_p, encoding="utf-8"))["loyaltyLevels"][-1]["minStanding"]
        _td_max = _t["levels"][-1].get("requiredReputation") or 0
        if _spt_max and _td_max:
            STANDING_RATIO[_t["id"]] = _spt_max / _td_max


def spt_standing(trader, value):
    """1.0 standing -> SPT scale using the trader's top loyalty threshold."""
    return round(value * STANDING_RATIO.get(trader, 1.0), 3)
td_items = json.load(open(f"{DATA}/items.json", encoding="utf-8"))["data"]
td_items = td_items.get("items", td_items)
td_items = td_items if isinstance(td_items, dict) else {x["id"]: x for x in td_items}
ctx.categories = {i: x["categories"][0] for i, x in td_items.items() if x.get("categories")}
# SPT's English text, to tell an objective 1.0 reworded from one it only renamed a zone of
SPT_TEXT = json.load(open(f"{SPT_DB}/locales/global/en.json", encoding="utf-8"))
traders_assort = {}
for tid in os.listdir(f"{SPT_DB}/traders"):
    p = f"{SPT_DB}/traders/{tid}/assort.json"
    if os.path.exists(p):
        traders_assort[tid] = json.load(open(p, encoding="utf-8"))

# WTT-ContentBackport sells fully built 1.0 items; treat its offers like SPT's.
WTT_DB = os.path.join(SPT_DB, "..", "..", "user", "mods", "WTT-ContentBackport", "db")
_nick = {}
for _tid in os.listdir(f"{SPT_DB}/traders"):
    _bp = f"{SPT_DB}/traders/{_tid}/base.json"
    if os.path.exists(_bp):
        _nick[json.load(open(_bp, encoding="utf-8"))["nickname"].lower()] = _tid
_nick["ref"] = "6617beeaa9cfa777ca915b7c"
wtt_assort = {}
_adir = os.path.join(WTT_DB, "CustomAssortSchemes")
if os.path.isdir(_adir):
    for _f in os.listdir(_adir):
        for _k, _blk in json.load(open(os.path.join(_adir, _f), encoding="utf-8-sig")).items():
            _tid = _nick.get(_k.lower(), _k)
            wtt_assort.setdefault(_tid, {"items": []})["items"] += _blk.get("items", [])

# Zone ids the 0.16.9 client already has (every zone some SPT quest uses).
KNOWN_ZONES = set()
for q in ctx.quests.values():
    for c in q["conditions"]["AvailableForFinish"]:
        if c.get("zoneId"):
            KNOWN_ZONES.add(c["zoneId"])
        for sc in (c.get("counter") or {}).get("conditions", []):
            if sc["conditionType"] in ("VisitPlace", "LaunchFlare"):
                KNOWN_ZONES.add(sc["target"])
            for z in sc.get("zoneIds") or []:
                KNOWN_ZONES.add(z)

report = {"new": [], "patched": [], "skipped": [], "zones": 0, "spawns": 0, "notes": []}
zones_out = []
spawns_out = {}
quest_assort = {}  # trader -> {"success": {assortId: questId}}


def name_of(qid):
    return TEXT.get(f"{qid} name") or ctx.quests.get(qid, {}).get("QuestName") or qid


# ---------------------------------------------------------------- rewards

def _remap_items(items, seed):
    idmap = {it["_id"]: mongo_id(seed, it["_id"]) for it in items}
    out = []
    for it in items:
        n = copy.deepcopy(it)
        n["_id"] = idmap[it["_id"]]
        if "parentId" in n:
            n["parentId"] = idmap.get(n["parentId"], n["parentId"])
        out.append(n)
    return out


def _default_preset(tpl):
    for p in ctx.presets.values():
        if p.get("_encyclopedia") == tpl:
            return p
    return None


def reward_items(tpl, count, seed):
    """Return (items, root id) for an item reward, expanding presets."""
    preset = ctx.presets.get(tpl)
    base_tpl = (preset.get("_encyclopedia") or preset["_items"][0]["_tpl"]) if preset else tpl
    if tpl in td_items and "preset" in (td_items[tpl].get("types") or []):
        contains = td_items[tpl].get("containsItems") or []
        base_tpl = contains[0]["item"] if contains else tpl
    if count == 1 and (preset is None or len(preset["_items"]) < 3):
        tree = built_tree(base_tpl, seed)
        if tree:
            return tree
    if preset is None and tpl in td_items and "preset" in (td_items[tpl].get("types") or []):
        contains = td_items[tpl].get("containsItems") or []
        base = contains[0]["item"] if contains else None
        preset = _default_preset(base) if base else None
        if preset is None and base in ctx.known_items:
            tpl = base
    if preset is not None:
        items = _remap_items(preset["_items"], seed)
        items[0].setdefault("upd", {})["StackObjectsCount"] = 1
        items[0].pop("parentId", None)
        items[0].pop("slotId", None)
        return items, items[0]["_id"]
    if tpl not in ctx.known_items:
        return None, None
    root = mongo_id(seed, tpl)
    return [{"_id": root, "_tpl": tpl, "upd": {"StackObjectsCount": count}}], root


def _base_reward(rtype, rid, **kw):
    r = {"availableInGameEditions": [], "gameMode": ["regular", "pve"], "id": rid, "isHidden": False, "type": rtype, "unknown": False}
    r.update(kw)
    return r


def convert_rewards(block, qid, stage, experience=0):
    out = []
    block = block or {}
    if experience:
        out.append(_base_reward("Experience", mongo_id(qid, stage, "xp"), value=experience))
    for i, s in enumerate(block.get("traderStanding") or []):
        out.append(_base_reward("TraderStanding", mongo_id(qid, stage, "ts", i), target=s["trader"], value=spt_standing(s["trader"], s["standing"])))
    for i, r in enumerate(block.get("items") or []):
        items, root = reward_items(r["item"], r["count"], (qid, stage, "item", i))
        if not items:
            ctx.warn(qid, f"reward item {r['item']} unknown, dropped")
            continue
        out.append(_base_reward(
            "Item", mongo_id(qid, stage, "item", i),
            findInRaid=r["item"] not in MONEY, isEncoded=False, items=items, target=root, value=r["count"],
        ))
    for i, u in enumerate(block.get("offerUnlock") or []):
        assort = find_assort(u["trader"], u["item"]) or new_assort(u, qid, i)
        if not assort:
            ctx.warn(qid, f"offer unlock {u['item']} at {u['trader']} unknown item, dropped")
            continue
        aid, items = assort
        rid = mongo_id(qid, stage, "unlock", i)
        shown = _remap_items(items, (qid, "unlock", i))
        for k in ("parentId", "slotId"):
            shown[0].pop(k, None)  # reward preview items are loose, not in the trader's "hideout"
        out.append(_base_reward(
            "AssortmentUnlock", rid, items=shown,
            loyaltyLevel=u.get("level", 1), target=mongo_id((qid, "unlock", i), items[0]["_id"]), traderId=u["trader"],
        ))
        quest_assort.setdefault(u["trader"], {}).setdefault("success", {})[aid] = qid
    for i, s in enumerate(block.get("skillLevelReward") or []):
        sk = s.get("skill")
        skill = sk.get("id") if isinstance(sk, dict) else sk or s.get("name")
        if not skill:
            ctx.warn(qid, f"{stage} skill reward {i} has no skill name, dropped")
            continue
        out.append(_base_reward("Skill", mongo_id(qid, stage, "skill", i), target=skill, value=int(s["level"] * 100)))
    for i, tr in enumerate(block.get("traderUnlock") or []):
        tid = tr if isinstance(tr, str) else tr.get("id")
        out.append(_base_reward("TraderUnlock", mongo_id(qid, stage, "tu", i), target=tid))
    for k in ("craftUnlock", "achievement", "customization"):
        if block.get(k):
            ctx.warn(qid, f"{stage} {k} reward not ported")
    for i, r in enumerate(out):
        r["index"] = i
    return out


new_assorts = {}  # trader -> WTT CustomAssortSchemes block


def _offer_price(tpl, trader):
    """1.0 trader price from tarkov.dev, else the item's base price in roubles."""
    item = td_items.get(tpl) or {}
    offers = item.get("buyFromTrader") or []
    for o in offers:
        if o.get("trader") == trader:
            return o["price"], o.get("currencyItem") or ROUBLES, o.get("buyLimit") or 0
    if offers:
        o = offers[0]
        return o["priceRUB"], ROUBLES, o.get("buyLimit") or 0
    return max(int((item.get("basePrice") or 10000) * 1.25), 1), ROUBLES, 0


def new_assort(u, qid, i):
    """1.0 unlocks offers SPT's traders don't stock; add the offer ourselves."""
    items, root = reward_items(u["item"], 1, (qid, "assort", i))
    if not items:
        return None
    price, currency, limit = _offer_price(u["item"], u["trader"])
    items[0]["parentId"] = "hideout"
    items[0]["slotId"] = "hideout"
    upd = items[0].setdefault("upd", {})
    upd.update({"UnlimitedCount": limit == 0, "StackObjectsCount": limit or 999999})
    if limit:
        upd["BuyRestrictionMax"] = limit
        upd["BuyRestrictionCurrent"] = 0
    block = new_assorts.setdefault(u["trader"], {"items": [], "barter_scheme": {}, "loyal_level_items": {}})
    block["items"] += items
    block["barter_scheme"][root] = [[{"count": price, "_tpl": currency}]]
    block["loyal_level_items"][root] = u.get("level", 1)
    report["notes"].append(f"{name_of(qid)}: added {u['trader'][:6]} LL{u.get('level', 1)} offer for {u['item']} at {price} {currency[:6]}")
    return root, [dict(it) for it in items]


def find_assort(trader, tpl):
    for a in (traders_assort.get(trader), wtt_assort.get(trader)):
        hit = _find_in(a, tpl)
        if hit:
            return hit
    return None


def built_tree(tpl, seed):
    """A fully assembled copy of tpl from any trader's stock (SPT or WTT)."""
    for a in list(traders_assort.values()) + list(wtt_assort.values()):
        hit = _find_in(a, tpl)
        if hit and len(hit[1]) > 1:
            items = _remap_items(hit[1], seed)
            items[0] = {k: v for k, v in items[0].items() if k not in ("parentId", "slotId")}
            items[0]["upd"] = {"StackObjectsCount": 1}
            return items, items[0]["_id"]
    return None


def _find_in(a, tpl):
    if not a:
        return None
    for it in a["items"]:
        if it["_tpl"] == tpl and it.get("parentId") == "hideout":
            children = [c for c in a["items"] if _is_child(a["items"], c, it["_id"])]
            return it["_id"], [it] + children
    return None


def _is_child(items, c, root):
    by = {i["_id"]: i for i in items}
    p = c.get("parentId")
    while p and p != "hideout":
        if p == root:
            return True
        p = by.get(p, {}).get("parentId")
    return False


# ---------------------------------------------------------------- objectives

NUM = {"a": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6}


def _count_in(text):
    m = re.search(r"\b(\d+|one|two|three|four|five|six)\b", text.lower())
    return int(m.group(1)) if m and m.group(1).isdigit() else NUM.get(m.group(1), 1) if m else 1


def substitute(o, qid, text):
    """Swap objectives SPT can't track for the closest raid equivalent.
    Returns (objective or None, new english text or None)."""
    t = o["type"]
    low = text.lower()
    if t == "visit" and not o.get("zones") and ("match" in low or "arena" in low):
        n = _count_in(text)
        return ({**o, "type": "extract", "count": n, "maps": [], "exitStatus": ["Survived"], "exitName": None},
                f"Survive and extract from any location ({text})")
    if t == "shoot" and "arena" in low:
        return ({**o, "maps": [], "zones": []}, "Eliminate any target on any location (originally: " + text + ")")
    if t == "dialogue":
        return ({**o, "type": "extract", "count": 1, "maps": ["5714dc692459777137212e12"], "exitStatus": ["Survived", "Runner"]},
                "Survive and extract from Streets of Tarkov (originally: " + text + ")")
    if t == "globalVariable":
        return None, None
    return o, None


def _map_name_text(text):
    return text.replace("on Icebreaker", "on Lighthouse").replace("Icebreaker", "Lighthouse")


def build_zone(z, ztype):
    m = ctx.map_id(z["map"])
    loc = ctx.loc_by_mongo.get(m)
    if not loc:
        return
    key = (z["id"], loc.lower())
    if any((x["ZoneId"], x["ZoneLocation"]) == key for x in zones_out):
        return
    p = z["position"]
    top, bottom = z.get("top"), z.get("bottom")
    if z.get("outline"):
        xs = [pt["x"] for pt in z["outline"]]
        zs = [pt["z"] for pt in z["outline"]]
        sx, sz = max(xs) - min(xs), max(zs) - min(zs)
        cx, cz = (max(xs) + min(xs)) / 2, (max(zs) + min(zs)) / 2
    elif z.get("size"):
        sx, sz, cx, cz = z["size"]["x"], z["size"]["z"], p["x"], p["z"]
    else:
        sx = sz = 3 if ztype == "placeitem" else 8
        cx, cz = p["x"], p["z"]
    sy = (top - bottom) if top is not None and bottom is not None else 3
    cy = (top + bottom) / 2 if top is not None and bottom is not None else p["y"]
    f = lambda v: f"{v:.4f}"  # noqa: E731
    zones_out.append({
        "ZoneId": z["id"], "ZoneName": z["id"], "ZoneLocation": loc.lower(), "ZoneType": ztype, "FlareType": "",
        "Position": {"X": f(cx), "Y": f(cy), "Z": f(cz), "W": "0"},
        "Rotation": {"X": "0", "Y": "0", "Z": "0", "W": "1"},
        "Scale": {"X": f(max(sx, 1)), "Y": f(max(sy, 1)), "Z": f(max(sz, 1)), "W": "0"},
    })
    report["zones"] += 1


ZONE_TYPE = {"visit": "visit", "plantItem": "placeitem", "plantQuestItem": "placeitem", "mark": "placeitem", "useItem": "flarezone", "shoot": "botkillzone"}


def ensure_zones(o):
    ztype = ZONE_TYPE.get(o["type"])
    if not ztype:
        return
    for z in o.get("zones") or []:
        if z["id"] not in KNOWN_ZONES or z["map"] in MAP_SUBSTITUTES:
            build_zone(z, ztype)


def ensure_spawns(o, qid):
    """Forced spawn for quest items the client has never placed on a map."""
    if o["type"] != "findQuestItem":
        return
    q = o["questItem"] if isinstance(o["questItem"], str) else o["questItem"]["id"]
    for pl in o.get("possibleLocations") or []:
        loc = ctx.loc_by_mongo.get(ctx.map_id(pl["map"]))
        if not loc:
            continue
        for i, pos in enumerate(pl["positions"]):
            root = mongo_id(qid, o["id"], loc, i, "root")
            spawns_out.setdefault(loc.lower(), []).append({
                "locationId": f"({pos['x']:.4f} {pos['y']:.4f} {pos['z']:.4f})",
                "probability": 1 / max(len(pl["positions"]), 1),
                "template": {
                    "Id": f"questbackport_{o['id']}_{i}",
                    "IsContainer": False, "useGravity": False, "randomRotation": False,
                    "Position": {"x": pos["x"], "y": pos["y"], "z": pos["z"]},
                    "Rotation": {"x": 0, "y": 0, "z": 0},
                    "IsGroupPosition": False, "GroupPositions": [], "IsAlwaysSpawn": True,
                    "Root": root,
                    "Items": [{"_id": root, "_tpl": q, "upd": {"StackObjectsCount": 1}}],
                },
            })
            report["spawns"] += 1


def one_session(text):
    return "in one raid" in text.lower()


def distance_from(text):
    m = re.search(r"from (?:over|at least|more than) (\d+) met", text.lower())
    return int(m.group(1)) if m else 0


def text_distance(o, text):
    """tarkov.dev sometimes reports 0 for a kill distance the text still has ("from over 50 meters")."""
    d = distance_from(text)
    if o["type"] == "shoot" and d and not (o.get("distance") or {}).get("value"):
        o["distance"] = {"compareMethod": ">=", "value": d}


def objectives_for(t, locale, ov=None):
    ov = OVERRIDES if ov is None else ov
    conds = []
    for i, o in enumerate(t["objectives"]):
        if o["id"] in ov.get("drop", []):
            continue
        o = dict(o)
        o.update(ov.get("objectives", {}).get(o["id"], {}))
        text = TEXT.get(o["id"]) or ""
        o, new_text = substitute(o, t["id"], text)
        if o is None:
            continue
        o["_oneSession"] = one_session(text)
        text_distance(o, text)
        ensure_zones(o)
        ensure_spawns(o, t["id"])
        c = convert_objective(o, t["id"], ctx, len(conds))
        if c is None:
            ctx.warn(t["id"], f"objective {o['id']} type {o['type']} not convertible, dropped")
            continue
        conds.append(c)
        locale[o["id"]] = ov.get("text", {}).get(o["id"]) or _map_name_text(new_text or text)
    return conds


# ---------------------------------------------------------------- quests

QUEST_TYPE = {"shoot": "Elimination", "giveItem": "PickUp", "findItem": "PickUp", "visit": "Exploration", "extract": "Exploration",
              "plantItem": "Completion", "mark": "Completion", "buildWeapon": "WeaponAssembly", "skill": "Skill"}


def start_conditions(t):
    out = []
    if t.get("minPlayerLevel"):
        out.append({"compareMethod": ">=", "conditionType": "Level", "dynamicLocale": False, "globalQuestCounterId": "",
                    "id": mongo_id(t["id"], "level"), "index": 0, "parentId": "", "value": t["minPlayerLevel"], "visibilityConditions": []})
    # one unlock delay per quest in 1.0 (Sensory Analysis - Part 1: 30-35 min after the previous quest)
    delay = t.get("availableDelaySecondsMin") or 0
    spread = max((t.get("availableDelaySecondsMax") or 0) - delay, 0)
    for r in t.get("taskRequirements") or []:
        target = r["task"] if isinstance(r["task"], str) else r["task"]["id"]
        if target in SKIP or (target not in ctx.quests and target not in TASK_IDS):
            ctx.warn(t["id"], f"prerequisite {target} not available, dropped")
            continue
        out.append({"availableAfter": delay, "conditionType": "Quest", "dispersion": spread, "dynamicLocale": False, "globalQuestCounterId": "",
                    "id": mongo_id(t["id"], "req", target), "index": len(out), "parentId": "",
                    "status": sorted({STATUS[s] for s in r.get("status") or ["complete"]}), "target": target, "visibilityConditions": []})
    for r in t.get("traderRequirements") or []:
        if r.get("requirementType") == "level":
            out.append({"compareMethod": r.get("compareMethod", ">="), "conditionType": "TraderLoyalty", "dynamicLocale": False,
                        "globalQuestCounterId": "", "id": r.get("id") or mongo_id(t["id"], "loyalty"), "index": len(out), "parentId": "",
                        "target": r["trader"], "value": r["value"], "visibilityConditions": []})
        elif r.get("requirementType") == "reputation":
            out.append({"compareMethod": r.get("compareMethod", ">="), "conditionType": "TraderStanding", "dynamicLocale": False,
                        "globalQuestCounterId": "", "id": mongo_id(t["id"], "standing", r["trader"]), "index": len(out), "parentId": "",
                        "target": r["trader"], "value": spt_standing(r["trader"], r["value"]), "visibilityConditions": []})
    # 1.0 unlocks these after a number of quests done at a trader loyalty level. The client gets the
    # loyalty level, the server (Mod.cs) counts the quests.
    for r in t.get("otherRequirements") or []:
        if r.get("type") != "globalVariable":
            continue
        ll = COUNTER_LL[r["variableId"]]
        wiki = WIKI.get(t["id"], {}).get("loyalty")
        if wiki is not None and wiki != ll:
            ctx.warn(t["id"], f"wiki says LL{wiki}, its quest counter says LL{ll}; using LL{ll}")
        if ll > 1:
            out.append({"compareMethod": ">=", "conditionType": "TraderLoyalty", "dynamicLocale": False, "globalQuestCounterId": "",
                        "id": mongo_id(t["id"], "loyalty", r["id"]), "index": len(out), "parentId": "",
                        "target": t["trader"], "value": ll, "visibilityConditions": []})
        if r.get("compareMethod", ">=") != ">=":
            ctx.warn(t["id"], f"quest counter compares with {r['compareMethod']}, treated as >=")
        QUEST_LOCKS[t["id"]] = {"trader": t["trader"], "level": ll, "count": r.get("value") or 0}
    return out


ICON_DIR = os.path.join(DATA, "icons")
icons_used = {}  # trader -> [icon paths]


def quest_image(qid, trader):
    """1.0 icon (from fetch_icons.ps1) if we have it, else one of the trader's existing icons."""
    jpg = os.path.join(ICON_DIR, f"{qid}.jpg")
    if os.path.exists(jpg):
        icons_used.setdefault(trader, []).append(jpg)
        return f"/files/quest/icon/{qid}.jpg"
    return trader_image(trader)


def trader_image(trader):
    for q in ctx.quests.values():
        if q["traderId"] == trader and q.get("image"):
            return q["image"]
    return "/files/quest/icon/59689ee586f7740d1570bbd5.jpg"


def quest_location(t):
    """The map a quest is listed under, "any" when it spans several."""
    loc = ctx.map_id(t["map"]) if t.get("map") else "any"
    return loc if loc in ctx.loc_by_mongo else "any"


def new_quest(t, ov=None):
    qid = t["id"]
    locale = {}
    conds = objectives_for(t, locale, ov)
    fail = []
    for i, o in enumerate(t.get("failConditions") or []):
        o, _ = substitute(dict(o), qid, TEXT.get(o["id"]) or "")
        if o is None or (o["type"] == "extract" and not o.get("maps")):
            continue  # Arena match-loss fail conditions have no raid equivalent
        c = convert_objective(o, qid, ctx, len(fail))
        if c:
            fail.append(c)
            locale[o["id"]] = TEXT.get(o["id"]) or ""
    loc = "any" if ov and ov.get("anyLocation") else quest_location(t)
    first = t["objectives"][0]["type"] if t["objectives"] else ""
    q = {
        "QuestName": name_of(qid), "_id": qid,
        "acceptPlayerMessage": f"{qid} acceptPlayerMessage", "acceptanceAndFinishingSource": "eft", "arenaLocations": [],
        "canShowNotificationsInGame": True, "changeQuestMessageText": f"{qid} changeQuestMessageText",
        "completePlayerMessage": f"{qid} completePlayerMessage",
        "conditions": {"AvailableForFinish": conds, "AvailableForStart": start_conditions(t), "Fail": fail},
        "declinePlayerMessage": f"{qid} declinePlayerMessage", "description": f"{qid} description",
        "failMessageText": f"{qid} failMessageText", "gameModes": [], "image": quest_image(qid, t["trader"]),
        "instantComplete": False, "isKey": False, "location": loc, "name": f"{qid} name", "note": f"{qid} note",
        "progressSource": "eft", "rankingModes": [], "restartable": bool(t.get("restartable")),
        "rewards": {
            "Fail": convert_rewards(t.get("failureOutcome"), qid, "fail"),
            "Started": convert_rewards(t.get("startRewards"), qid, "start"),
            "Success": convert_rewards(t.get("finishRewards"), qid, "finish", t.get("experience") or 0),
        },
        "secretQuest": False, "side": "Pmc", "startedMessageText": f"{qid} startedMessageText", "status": 0,
        "successMessageText": f"{qid} successMessageText", "traderId": t["trader"],
        "type": QUEST_TYPE.get(first, "Completion"),
    }
    w = WIKI.get(qid, {})
    name = name_of(qid).replace(" [PVP ZONE]", "")
    locale.update({
        f"{qid} name": name,
        f"{qid} description": w.get("description") or f"{name}. (Backported from Escape from Tarkov 1.0.)",
        f"{qid} successMessageText": w.get("success") or "Good work. Here's what I promised.",
        f"{qid} failMessageText": w.get("fail") or "",
        f"{qid} startedMessageText": "",
        f"{qid} acceptPlayerMessage": "", f"{qid} declinePlayerMessage": "", f"{qid} completePlayerMessage": "",
        f"{qid} changeQuestMessageText": "", f"{qid} note": "",
    })
    return q, locale


def patch_quest(t):
    """Apply 1.0 numbers to a quest SPT already has, keeping every id."""
    qid = t["id"]
    q = copy.deepcopy(ctx.quests[qid])
    changes = []
    by_id = {c["id"]: c for c in q["conditions"]["AvailableForFinish"]}
    # level requirement
    for c in q["conditions"]["AvailableForStart"]:
        if c["conditionType"] == "Level" and t.get("minPlayerLevel") and c["value"] != t["minPlayerLevel"]:
            changes.append(f"level {c['value']}->{t['minPlayerLevel']}")
            c["value"] = t["minPlayerLevel"]
    _patch_unlocks(q, t, changes)
    # the map the quest is listed under (Administrator moved from Streets to Reserve).
    # BSG lists transit quests under "marathon", which tarkov.dev reports as any.
    loc = quest_location(t)
    if q.get("location") not in ("marathon", loc):
        changes.append(f"listed on {ctx.loc_by_mongo.get(q['location'], q['location'])}->{ctx.loc_by_mongo.get(loc, loc)}")
        q["location"] = loc
    locale = {}
    td_ids = set()
    for i, o in enumerate(t["objectives"]):
        if o["id"] in OVERRIDES.get("drop", []):
            continue
        o = {**o, **OVERRIDES.get("objectives", {}).get(o["id"], {})}
        td_ids.add(o["id"])
        text = TEXT.get(o["id"]) or ""
        shown = OVERRIDES.get("text", {}).get(o["id"])
        old = by_id.get(o["id"])
        if old is None:
            o2, new_text = substitute(dict(o), qid, text)
            if o2 is None:
                continue
            o2["_oneSession"] = one_session(text)
            text_distance(o2, text)
            ensure_zones(o2)
            ensure_spawns(o2, qid)
            c = convert_objective(o2, qid, ctx, len(q["conditions"]["AvailableForFinish"]))
            if c:
                q["conditions"]["AvailableForFinish"].append(c)
                locale[o["id"]] = shown or _map_name_text(new_text or text)
                changes.append(f"+objective {o['type']}")
            continue
        new = convert_objective({**o, "_oneSession": old.get("oneSessionOnly", False)}, qid, ctx, old.get("index", i))
        if new is None:
            continue
        if new.get("value") is not None and old.get("value") != new["value"]:
            changes.append(f"{o['type']} count {old.get('value')}->{new['value']}")
            old["value"] = new["value"]
        if old["conditionType"] in ("HandoverItem", "FindItem", "LeaveItemAtLocation") and new["conditionType"] == old["conditionType"]:
            tgt = ctx.known(new["target"])
            if tgt and sorted(tgt) != sorted(old["target"]):
                changes.append(f"{o['type']} items changed")
                old["target"] = tgt
            # tarkov.dev has Trophies' dog tags as not found in raid; its 1.0 text still asks for it
            fir = bool(new.get("onlyFoundInRaid")) or "found in raid" in text.lower()
            if old.get("onlyFoundInRaid") != fir:
                changes.append(f"FIR {old.get('onlyFoundInRaid')}->{fir}")
                old["onlyFoundInRaid"] = fir
        # "sell any backpacks" lists gained 1.0's new items. Only add: tarkov.dev's lists are partial.
        if old["conditionType"] == "SellItemToTrader" and new["conditionType"] == old["conditionType"]:
            extra = [i for i in ctx.known(new["target"]) if i not in old["target"]]
            if extra:
                changes.append(f"+{len(extra)} items to sell")
                old["target"] = old["target"] + extra
        # Sew it Good dropped its armor durability ranges, Trophies takes level 20+ dog tags
        if old["conditionType"] in ("HandoverItem", "FindItem") and new["conditionType"] == old["conditionType"]:
            for k in ("minDurability", "maxDurability", "dogtagLevel"):
                if old.get(k, new[k]) != new[k]:
                    changes.append(f"{k} {old[k]}->{new[k]}")
                    old[k] = new[k]
        # 1.0 moved some plant spots (Golden Swag: portable cabin -> dorm 303)
        if old["conditionType"] in ("LeaveItemAtLocation", "PlaceBeacon") and new["conditionType"] == old["conditionType"]:
            new_zones = [z["id"] for z in o.get("zones") or []]
            if new_zones and old.get("zoneId") not in new_zones:
                ensure_zones(o)
                changes.append(f"zone {old.get('zoneId')}->{new['zoneId']}")
                old["zoneId"] = new["zoneId"]
        if old["conditionType"] == "CounterCreator" and new["conditionType"] == "CounterCreator":
            # tarkov.dev only says "in one raid" in the text (Stray Dogs, Administrator)
            if one_session(text) and not old.get("oneSessionOnly"):
                changes.append("in one raid")
                old["oneSessionOnly"] = True
            _patch_counter(qid, old, new, o, changes, text)
        # 1.0 eased most Gunsmith specs (Gunsmith Master - Part 4: ergonomics 70->53, recoil 250->300)
        if old["conditionType"] == "WeaponAssembly" and new["conditionType"] == "WeaponAssembly":
            attrs = o.get("buildAttributes") or {}
            for k, key in BUILD_ATTRS.items():
                if attrs.get(k) and new[key] != old.get(key):
                    changes.append(f"{k} {(old.get(key) or {}).get('value')}->{new[key]['value']}")
                    old[key] = new[key]
        if shown or text:
            locale[o["id"]] = shown or _map_name_text(text)
    # objectives 1.0 removed
    if td_ids:
        keep = [c for c in q["conditions"]["AvailableForFinish"] if c["id"] in td_ids or c["id"] in {x for x in locale}]
        removed = len(q["conditions"]["AvailableForFinish"]) - len(keep)
        if removed:
            changes.append(f"-{removed} objective(s)")
            q["conditions"]["AvailableForFinish"] = keep
            # a kept objective can be hidden until a removed one is done; the client's quest list breaks on the missing target
            ids = {c["id"] for c in keep}
            for c in keep:
                vis = c.get("visibilityConditions") or []
                if any(v.get("target") not in ids for v in vis):
                    c["visibilityConditions"] = [v for v in vis if v.get("target") in ids]
                    changes.append("unhid objective that waited on a removed one")
    _patch_rewards(q, t, changes)
    if t.get("name") and TEXT.get(f"{qid} name"):
        locale[f"{qid} name"] = TEXT[f"{qid} name"]
    return q, locale, changes


TRADER_NAME = {tid: nick for nick, tid in _nick.items()}


def _unlock_name(c):
    if c["conditionType"] == "Quest":
        return name_of(c["target"])
    trader = TRADER_NAME.get(c["target"], c["target"][:6])
    if c["conditionType"] == "TraderLoyalty":
        return f"{trader} LL{c['value']}"
    return f"{trader} standing {c['compareMethod']}{c['value']}"


def _unlock_sig(c):
    return sorted(c.get("status") or []), c.get("availableAfter") or 0, c.get("dispersion") or 0, c.get("compareMethod"), c.get("value")


def _patch_unlocks(q, t, changes):
    """1.0's prerequisite quests, trader loyalty and standing gates and unlock delays, keeping SPT's ids.
    Quests 1.0 unlocks once enough quests are done at a loyalty level also land in QUEST_LOCKS."""
    start = q["conditions"]["AvailableForStart"]
    before = {(c["conditionType"], c.get("target")): copy.deepcopy(c) for c in start}
    old = {(c["conditionType"], c.get("target")): c for c in start}
    out = [c for c in start if c["conditionType"] == "Level"]
    for c in start_conditions(t):
        if c["conditionType"] == "Level":
            continue
        key = (c["conditionType"], c["target"])
        prev = old.get(key)
        if prev is None:
            changes.append(f"unlock +{_unlock_name(c)}")
        else:
            # SPT's standing values stay: they're the same as 1.0's where both have one
            for k in ("status", "availableAfter", "dispersion", "compareMethod") + (("value",) if c["conditionType"] == "TraderLoyalty" else ()):
                if k in c:
                    prev[k] = c[k]
            if _unlock_sig(prev) != _unlock_sig(before[key]):
                changes.append(f"unlock changed {_unlock_name(prev)}")
            c = prev
        out.append(c)
    kept = {(c["conditionType"], c.get("target")) for c in out}
    for key, c in before.items():
        if key not in kept:
            changes.append(f"unlock -{_unlock_name(c)}")
    if t["id"] in QUEST_LOCKS:
        changes.append(f"unlock after {QUEST_LOCKS[t['id']]['count']} quests at LL{QUEST_LOCKS[t['id']]['level']}")
    for i, c in enumerate(out):
        c["index"] = i
    q["conditions"]["AvailableForStart"] = out


BUILD_ATTRS = {k: k for k in ("durability", "effectiveDistance", "ergonomics", "height", "magazineCapacity",
                              "muzzleVelocity", "recoil", "weight", "width")} | {"accuracy": "baseAccuracy"}


# the 1.0 text still asks for a weapon part, a spot on the map, or names the maps
MOD_WORDS = re.compile(r"suppress|silenc|scope|sight|muzzle|barrel|stock|foregrip|tactical device", re.I)
PLACE_WORDS = re.compile(r"\b(?:at|inside|around|near|along|in) the\b", re.I)
MAP_WORDS = {"bigmap": "customs", "Woods": "woods", "Shoreline": "shoreline", "Interchange": "interchange",
             "RezervBase": "reserve", "Lighthouse": "lighthouse", "TarkovStreets": "streets of tarkov",
             "Sandbox": "ground zero", "Sandbox_high": "ground zero", "laboratory": "the lab",
             "factory4_day": "factory", "factory4_night": "factory", "Labyrinth": "labyrinth"}


def _groups(groups):
    return sorted(tuple(sorted(g)) for g in groups)


def _ids(group):
    return [g["id"] if isinstance(g, dict) else g for g in group]


def _reworded(oid, text):
    """1.0 changed what the objective says, not just the id of a zone behind the same words."""
    old = SPT_TEXT.get(oid)
    return bool(text and old) and old != text


def _patch_counter(qid, old, new, o, changes, text=""):
    subs = old["counter"]["conditions"]
    olds = {sc["conditionType"]: sc for sc in subs}
    for sc in new["counter"]["conditions"]:
        prev = olds.get(sc["conditionType"])
        if prev is None:
            continue
        if sc["conditionType"] == "Location" and sorted(prev["target"]) != sorted(sc["target"]):
            changes.append(f"map {prev['target']}->{sc['target']}")
            prev["target"] = sc["target"]
        if sc["conditionType"] in ("Kills", "Shots"):
            _patch_kill(prev, sc, o, changes, text)
    if o["type"] == "shoot":
        _patch_gear(qid, subs, o, changes, text)
        _patch_kill_zone(qid, subs, o, changes, text)
    _patch_place(subs, o, changes, text)
    # after the zones: a kill zone 1.0 dropped may have been all that held the map
    _patch_map(qid, subs, o, changes, text)


def _patch_kill(prev, sc, o, changes, text):
    # 1.0 swapped many weapons (One-Way Ticket: 12ga shotguns -> AUG). SPT's extras stay only when
    # tarkov.dev doesn't know the item (event melee, the GP-34), since 1.0's list couldn't name it.
    if sc["weapon"]:
        weapons = list(dict.fromkeys(sc["weapon"] + [w for w in prev.get("weapon") or [] if w not in td_items]))
        if sorted(weapons) != sorted(prev.get("weapon") or []):
            changes.append("weapon list updated")
            prev["weapon"] = weapons
    # The Good Times - Part 1 no longer wants an M4A1, Claustrophobia no longer wants a shotgun
    elif prev.get("weapon") and _reworded(o["id"], text) and not re.search(r"\b(?:with|using)\b", text, re.I):
        changes.append("weapon list removed")
        prev["weapon"] = []
    # the sight on Getting Some Air, the suppressor Wet Job - Part 1 no longer wants
    have = prev.get("weaponModsInclusive") or []
    mods = sc["weaponModsInclusive"]
    if mods:
        mods = mods + [g for g in have if g and not any(m in td_items for m in g) and g not in mods]
        if _groups(mods) != _groups(have):
            changes.append("weapon mods updated")
            prev["weaponModsInclusive"] = mods
    elif not o.get("usingWeaponMods") and any(have) and text and not MOD_WORDS.search(text):
        changes.append("weapon mods removed")
        prev["weaponModsInclusive"] = []
    if sorted(sc["bodyPart"]) != sorted(prev.get("bodyPart") or []):
        changes.append(f"body parts {prev.get('bodyPart')}->{sc['bodyPart']}")
        prev["bodyPart"] = sc["bodyPart"]
    # tarkov.dev sometimes reports 0 for a distance the text still has ("from over 50 meters")
    dist = sc["distance"] if sc["distance"]["value"] else {"compareMethod": ">=", "value": distance_from(text)}
    # only drop a limit when the 1.0 text agrees (Tarkov Shooter - Part 4 lost its 80 m)
    old_dist = (prev.get("distance") or {}).get("value") or 0
    if (dist["value"] or (text and old_dist)) and dist != prev.get("distance"):
        changes.append(f"distance {old_dist}->{dist['value']}")
        prev["distance"] = dist
    # tarkov.dev reports both "any target" and some specific kills as "Any";
    # only trust "Any" when the 1.0 objective text says so too.
    trusted = sc["target"] != "Any" or "any target" in text.lower()
    if trusted and (sc["target"], sc["savageRole"]) != (prev.get("target"), prev.get("savageRole")):
        changes.append(f"target {prev.get('target')}{prev.get('savageRole') or ''}->{sc['target']}{sc['savageRole'] or ''}")
        prev["target"], prev["savageRole"] = sc["target"], sc["savageRole"]


def _patch_map(qid, subs, o, changes, text):
    """Add or drop the map limit. tarkov.dev also lists where a boss spawns, so a map is only added
    when the 1.0 text names it, and only dropped when 1.0 lists no map at all."""
    if any(s["conditionType"] in ("InZone", "VisitPlace", "LaunchFlare", "ExitName") for s in subs):
        return  # the zone or exit already pins the map
    loc = next((s for s in subs if s["conditionType"] == "Location"), None)
    want = _location_sub(o, qid, ctx)
    low = text.lower()
    if loc is None and want and all(MAP_WORDS.get(n, "\0") in low for n in want[0]["target"]):
        subs.append(want[0])
        changes.append(f"map any->{want[0]['target']}")
    elif loc is not None and text and not o.get("maps") and not any(w in low for w in MAP_WORDS.values()):
        subs.remove(loc)
        changes.append(f"map {loc['target']}->any")


def _patch_gear(qid, subs, o, changes, text):
    """Gear the player has to wear or must not wear (Punisher - Part 4 no longer wants a balaclava)."""
    eq = [s for s in subs if s["conditionType"] == "Equipment"]
    inc = [s for s in eq if s.get("equipmentInclusive")]
    want = [g for g in (ctx.known(_ids(grp)) for grp in o.get("wearing") or []) if g]
    have = [g for s in inc for g in s["equipmentInclusive"]]
    if want and _groups(want) != _groups(have):
        at = subs.index(inc[0]) if inc else len(subs)
        for s in inc:
            subs.remove(s)
        for i, groups in enumerate(wearing_groups(want, ctx)):
            s = copy.deepcopy(inc[i]) if i < len(inc) else _equipment_sub(qid, o["id"], f"wear{i}")
            s["equipmentInclusive"] = groups
            subs.insert(at + i, s)
        changes.append("gear to wear updated")
    elif not o.get("wearing") and inc and text and "wear" not in text.lower():
        for s in inc:
            subs.remove(s)
        changes.append("gear to wear removed")
    # Unprotected but Dangerous now bans plate carriers too
    exc = [s for s in eq if s.get("equipmentExclusive")]
    had = [g for s in exc for g in s["equipmentExclusive"]]
    banned = ctx.known(_ids(o.get("notWearing") or []))
    if banned and all(len(g) == 1 for g in had):
        banned = list(dict.fromkeys(banned + [g[0] for g in had if g[0] not in td_items]))
        if sorted(banned) != sorted(g[0] for g in had):
            if exc:
                exc[0]["equipmentExclusive"] = [[i] for i in banned]
                for s in exc[1:]:
                    subs.remove(s)
            else:
                subs.append(_equipment_sub(qid, o["id"], "notwear", exclusive=[[i] for i in banned]))
            changes.append("gear not to wear updated")


SAME_MAP = {"factory4_night": "factory4_day", "Sandbox_high": "Sandbox"}


def _maps_of(names):
    return {SAME_MAP.get(n, n) for n in names}


def _spt_maps(qid, oid):
    """The maps an objective is on in SPT: its Location, else the quest's own map."""
    q = ctx.quests[qid]
    c = next((c for c in q["conditions"]["AvailableForFinish"] if c["id"] == oid), {})
    loc = next((s for s in c.get("counter", {}).get("conditions", []) if s["conditionType"] == "Location"), None)
    if loc:
        return _maps_of(loc["target"])
    name = ctx.loc_by_mongo.get(q.get("location"))
    return _maps_of([name]) if name else set()


def _patch_kill_zone(qid, subs, o, changes, text):
    """Where kills count. Only when 1.0 reworded the objective, some zones were just renamed.
    SPT's zone stays next to 1.0's so nothing that counts today stops counting, unless the
    objective moved to another map (Administrator: Pinewood hotel -> Reserve train depot)."""
    if not _reworded(o["id"], text):
        return
    zone = next((s for s in subs if s["conditionType"] == "InZone"), None)
    want = _zone_ids(o)
    if want:
        same_map = _spt_maps(qid, o["id"]) <= _maps_of(ctx.location_names([z["map"] for z in o["zones"]]))
        ids = list(dict.fromkeys((zone["zoneIds"] if zone and same_map else []) + want))
        if zone is None or ids != zone["zoneIds"]:
            ensure_zones(o)
            changes.append(f"kill zone {zone['zoneIds'] if zone else 'any'}->{ids}")
            if zone is None:
                subs.append({"conditionType": "InZone", "dynamicLocale": False, "id": mongo_id(qid, o["id"], "inzone"), "zoneIds": ids})
            else:
                zone["zoneIds"] = ids
    elif zone and not PLACE_WORDS.search(text):
        subs.remove(zone)
        changes.append(f"kill zone {zone['zoneIds']}->any")


def _patch_place(subs, o, changes, text):
    """A visit or flare spot 1.0 moved (Administrator: Pinewood hotel -> Reserve train depot)."""
    want = _zone_ids(o)
    for ct in ("VisitPlace", "LaunchFlare"):
        mine = [s for s in subs if s["conditionType"] == ct]
        if len(mine) == 1 and len(want) == 1 and mine[0]["target"] != want[0] and _reworded(o["id"], text):
            ensure_zones(o)
            changes.append(f"zone {mine[0]['target']}->{want[0]}")
            mine[0]["target"] = want[0]


def _sync_item_rewards(q, fin, changes):
    """Make non-money item rewards match 1.0. Craft and offer unlocks are kept:
    hideout recipes and trader offers are locked behind them."""
    qid = q["_id"]
    want = {}
    for r in fin.get("items") or []:
        if r["item"] not in MONEY:
            want[r["item"]] = want.get(r["item"], 0) + r["count"]
    succ = q["rewards"]["Success"]
    kept = []
    for r in succ:
        if r["type"] != "Item" or not r["items"] or r["items"][0]["_tpl"] in MONEY:
            kept.append(r)
            continue
        tpl = r["items"][0]["_tpl"]
        # rewards can be stored as a preset id in tarkov.dev; match on the root item
        match = tpl if tpl in want else next((w for w in want if _root_tpl(w) == tpl), None)
        if match is None:
            changes.append(f"-reward {tpl}")
            continue
        if r["value"] != want[match] and len(r["items"]) == 1:
            changes.append(f"reward {tpl} x{r['value']}->x{want[match]}")
            r["value"] = want[match]
            r["items"][0].setdefault("upd", {})["StackObjectsCount"] = want[match]
        want.pop(match)
        kept.append(r)
    for i, (tpl, count) in enumerate(want.items()):
        items, root = reward_items(tpl, count, (qid, "sync", i))
        if not items:
            ctx.warn(qid, f"1.0 reward {tpl} unknown, not added")
            continue
        kept.append(_base_reward("Item", mongo_id(qid, "sync", i), findInRaid=True, isEncoded=False,
                                 items=items, target=root, value=count))
        changes.append(f"+reward {tpl}")
    for i, r in enumerate(kept):
        r["index"] = i
    q["rewards"]["Success"] = kept


def _reward_roots(r):
    """A reward's items as one list per copy: [root, child, child...]."""
    by_parent = {}
    for it in r["items"]:
        by_parent.setdefault(it.get("parentId"), []).append(it)
    ids = {it["_id"] for it in r["items"]}

    def tree(root):
        out = [root]
        for c in by_parent.get(root["_id"], []):
            out += tree(c)
        return out
    return [tree(it) for it in r["items"] if it.get("parentId") not in ids]


def _set_count(r, count, seed):
    """SPT stores a stack as one item, and anything that doesn't stack as one copy per count."""
    copies = _reward_roots(r)
    if len(copies) == 1 and len(r["items"]) == 1 and ctx.items.get(r["items"][0]["_tpl"], {}).get("_props", {}).get("StackMaxSize", 1) > 1:
        r["items"][0].setdefault("upd", {})["StackObjectsCount"] = count
    else:
        for c in copies:
            c[0].setdefault("upd", {})["StackObjectsCount"] = 1
        while len(copies) < count:
            copies.append(_remap_items(copies[0], (seed, "copy", len(copies))))
        r["items"] = [it for c in copies[:count] for it in c]
        r["target"] = r["items"][0]["_id"]
    r["value"] = count


def _sync_start_rewards(q, t, changes):
    """Items handed over when the quest is accepted. 1.0 swapped many of them, often together
    with the objective that uses them (Fishing Gear: SV-98 -> MF-UNTAR body armor)."""
    qid = q["_id"]
    want = {}
    for r in (t.get("startRewards") or {}).get("items") or []:
        want[r["item"]] = want.get(r["item"], 0) + r["count"]
    kept = []
    for r in q["rewards"]["Started"]:
        if r["type"] != "Item" or not r["items"]:
            kept.append(r)
            continue
        tpl = next((i["_tpl"] for i in r["items"] if i["_id"] == r["target"]), r["items"][0]["_tpl"])
        match = tpl if tpl in want else next((w for w in want if _root_tpl(w) == tpl), None)
        if match is None:
            changes.append(f"-start item {tpl}")
            continue
        if r["value"] != want[match]:
            changes.append(f"start item {tpl} x{r['value']}->x{want[match]}")
            _set_count(r, want[match], (qid, "start", tpl))
        want.pop(match)
        kept.append(r)
    for i, (tpl, count) in enumerate(want.items()):
        items, root = reward_items(tpl, 1, (qid, "startsync", i))
        if not items:
            ctx.warn(qid, f"1.0 start item {tpl} unknown, not added")
            continue
        r = _base_reward("Item", mongo_id(qid, "startsync", i), findInRaid=tpl not in MONEY, isEncoded=False,
                         items=items, target=root, value=1)
        if count != 1:
            _set_count(r, count, (qid, "startsync", i))
        kept.append(r)
        changes.append(f"+start item {tpl}")
    for i, r in enumerate(kept):
        r["index"] = i
    q["rewards"]["Started"] = kept


def _root_tpl(tpl):
    p = ctx.presets.get(tpl)
    if p:
        return p.get("_encyclopedia") or p["_items"][0]["_tpl"]
    contains = (td_items.get(tpl) or {}).get("containsItems") or []
    return contains[0]["item"] if contains and "preset" in (td_items.get(tpl, {}).get("types") or []) else tpl


def _patch_rewards(q, t, changes):
    succ = q["rewards"]["Success"]
    xp = t.get("experience") or 0
    for r in succ:
        if r["type"] == "Experience" and xp and r["value"] != xp:
            changes.append(f"xp {r['value']}->{xp}")
            r["value"] = xp
    fin = (t.get("finishRewards") or {})
    money = {r["item"]: r["count"] for r in fin.get("items") or [] if r["item"] in MONEY}
    for r in succ:
        if r["type"] == "Item" and r["items"] and r["items"][0]["_tpl"] in money:
            tpl = r["items"][0]["_tpl"]
            if r["value"] != money[tpl]:
                changes.append(f"money {r['value']}->{money[tpl]}")
                r["value"] = money[tpl]
                r["items"][0].setdefault("upd", {})["StackObjectsCount"] = money[tpl]
    _sync_item_rewards(q, fin, changes)
    _sync_start_rewards(q, t, changes)
    # Standing is left alone: 1.0 rescaled trader loyalty ~10x, SPT still uses the old scale.


# ---------------------------------------------------------------- optional mods

def build_optional(db, write_locales):
    """db/Optional/<mod guid>/: quests that replace ours when that mod is loaded.
    Mod.cs reads index.json and applies the entries in order."""
    root = os.path.join(db, "Optional")
    shutil.rmtree(root, ignore_errors=True)
    entries = OVERRIDES.get("optional") or []
    if not entries:
        return
    by_id = {t["id"]: t for t in tasks}
    keep = copy.deepcopy((report, ctx.warnings))  # variant builds must not count twice
    index, summary = [], []
    for e in entries:
        base = os.path.join(root, e["mod"])
        os.makedirs(base, exist_ok=True)
        by_dir = {}  # trader folder -> (quests, english text)
        for qid in e.get("quests", []):
            q, locale = new_quest(by_id[qid], e)
            quests, english = by_dir.setdefault(os.path.join(base, "CustomQuests", q["traderId"]), ({}, {}))
            quests[qid] = q
            english.update(locale)
        for d, (quests, english) in by_dir.items():
            os.makedirs(os.path.join(d, "Quests"), exist_ok=True)
            json.dump(quests, open(os.path.join(d, "Quests", "quests.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
            write_locales(d, english)
        for qid in e.get("replaces", {}):
            for t in tasks:
                reqs = [r["task"] if isinstance(r["task"], str) else r["task"]["id"] for r in t.get("taskRequirements") or []]
                if qid in reqs and t["id"] not in e["replaces"]:
                    raise SystemExit(f"{name_of(t['id'])} needs {name_of(qid)}, which {e['mod']} replaces; remap it first")
        if e.get("replaces"):
            json.dump(e["replaces"], open(os.path.join(base, "replaces.json"), "w"), indent=1)
        index.append({"mod": e["mod"], "name": e["name"], "note": e.get("note", "")})
        summary.append({"mod": e["mod"], "quests": [name_of(q) for q in e.get("quests", [])], "replaces": [name_of(q) for q in e.get("replaces", {})]})
    json.dump(index, open(os.path.join(root, "index.json"), "w", encoding="utf-8"), indent=1)
    report.clear()
    report.update(keep[0])
    ctx.warnings[:] = keep[1]
    report["optional"] = summary


def old_order(spt, final):
    """Quests 1.0 moved ahead of their old prerequisite (The Punisher - Part 1 was SPT's Part 3). A profile
    already past the quest the old way keeps the old order: while it has the old prerequisite or a quest
    between the two, the quest waits for that prerequisite. Fresh profiles get 1.0's order.
    Returns (old order per quest, the (quest, prerequisite) pairs that only count the prerequisite itself)."""
    def reqs(db, qid):
        return {c["target"] for c in db[qid]["conditions"]["AvailableForStart"] if c["conditionType"] == "Quest"}

    def walk(step, qid):
        out, todo = set(), [qid]
        while todo:
            for n in step(todo.pop()):
                if n not in out and n != qid:
                    out.add(n)
                    todo.append(n)
        return out

    needs = {}  # quest -> the quests that need it in 1.0
    for qid in final:
        for r in reqs(final, qid):
            needs.setdefault(r, set()).add(qid)
    out, skipped = {}, []
    for qid in sorted(set(spt) & set(final)):
        later = walk(lambda x: needs.get(x, ()), qid)
        after, on_way = {}, set()
        for c in spt[qid]["conditions"]["AvailableForStart"]:
            r = c.get("target")
            if c["conditionType"] != "Quest" or r in reqs(final, qid) or r not in later:
                continue
            between = walk(lambda x: reqs(spt, x) if x in spt else (), r) & later
            # a quest between only counts when the old prerequisite still unlocks without this quest,
            # or the profile is stuck. Having the prerequisite itself is always safe
            if walk(lambda x: reqs(final, x) if x in final else (), r) & later - between:
                skipped.append((qid, r))
                between = set()
            after[r] = sorted(c.get("status") or [4])
            on_way |= between | {r}
        if after:
            out[qid] = {"after": after, "later": sorted(on_way)}
    return out, skipped


def write_tiers(db, by_trader):
    """db/QuestTiers.json for Mod.cs: the quests 1.0 unlocks once N quests are done for a trader at a
    loyalty level, and per trader and level the quests that count, by the level they unlock at."""
    final = dict(ctx.quests)
    for quests in by_trader.values():
        final.update(quests)
    counted = {}
    for qid, q in final.items():
        if qid in SKIP:
            continue
        lock = QUEST_LOCKS.get(qid)
        own = [c["value"] for c in q["conditions"]["AvailableForStart"] if c["conditionType"] == "TraderLoyalty" and c["target"] == q["traderId"]]
        ll = lock["level"] if lock else max([1] + own)
        counted.setdefault(q["traderId"], {}).setdefault(str(ll), []).append(qid)
    # play it through: every quest has to unlock at some point
    req = {qid: [c["target"] for c in q["conditions"]["AvailableForStart"] if c["conditionType"] == "Quest"] for qid, q in final.items()}
    done, grew = set(), True
    while grew:
        grew = False
        for qid, rs in req.items():
            if qid in done or not all(r in done for r in rs):
                continue
            lock = QUEST_LOCKS.get(qid)
            if lock and sum(x in done for x in counted.get(lock["trader"], {}).get(str(lock["level"]), [])) < lock["count"]:
                continue
            done.add(qid)
            grew = True
    for qid in final:
        if qid not in done:
            ctx.warn(qid, f"{name_of(qid)} can never unlock")
    # a 1.0 prerequisite SPT didn't have must not be a quest players can fail for good (a branch they
    # didn't pick), or profiles that failed it lose the quest
    failable = {qid for qid, q in final.items() if q["conditions"].get("Fail") and not q.get("restartable")}
    failable |= {c["target"] for q in final.values() for c in q["conditions"].get("Fail") or [] if c.get("conditionType") == "Quest"}
    for qid, q in final.items():
        before = {c["target"] for c in (ctx.quests.get(qid) or {}).get("conditions", {}).get("AvailableForStart", []) if c["conditionType"] == "Quest"}
        for c in q["conditions"]["AvailableForStart"]:
            if c["conditionType"] == "Quest" and qid in ctx.quests and c["target"] not in before and c["target"] in failable and 5 not in c["status"]:
                ctx.warn(qid, f"{name_of(qid)} now needs {name_of(c['target'])}, which can be failed for good")
    locks = {qid: QUEST_LOCKS[qid] for qid in sorted(QUEST_LOCKS) if qid in final}
    reordered, stuck = old_order(ctx.quests, final)
    for qid, r in stuck:
        ctx.warn(qid, f"{name_of(qid)} only keeps the old order for profiles that already have {name_of(r)}, it needs {name_of(qid)} in 1.0")
    for qid, o in reordered.items():
        ctx.warn(qid, f"{name_of(qid)} keeps the old order for profiles already past it, after {', '.join(name_of(r) for r in o['after'])}")
    json.dump({"locks": locks, "counted": counted, "oldOrder": reordered}, open(os.path.join(db, "QuestTiers.json"), "w"), indent=1)
    report["tiers"] = len(locks)
    report["old_order"] = len(reordered)


# ---------------------------------------------------------------- main

def main():
    db = os.path.join(OUT, "db")
    for sub in ("CustomQuests", "CustomQuestZones", "CustomLootspawns"):
        shutil.rmtree(os.path.join(db, sub), ignore_errors=True)
    by_trader = {}
    locales = {}
    for t in tasks:
        qid = t["id"]
        if qid in SKIP:
            report["skipped"].append(f"{name_of(qid)} ({qid}): prestige quest")
            continue
        if qid in REF_FRIENDLY:
            report["skipped"].append(f"{name_of(qid)} ({qid}): owned by RefFriendlyQuests")
            continue
        if qid in ctx.quests:
            q, loc, changes = patch_quest(t)
            if not changes:
                continue
            report["patched"].append({"id": qid, "name": name_of(qid), "changes": changes})
        else:
            q, loc = new_quest(t)
            report["new"].append({"id": qid, "name": name_of(qid), "objectives": len(q["conditions"]["AvailableForFinish"])})
        by_trader.setdefault(q["traderId"], {})[qid] = q
        locales.setdefault(q["traderId"], {}).update(loc)

    translations.write_template({k: v for loc in locales.values() for k, v in loc.items() if v})
    translated = {code: translations.read(code) for code in translations.languages()}
    report["translations"] = {}
    # Without a file per language WTT shows en.json to everyone, which would turn the
    # quests we only patched from Russian, Korean etc. into English. So write every
    # language SPT has, falling back to SPT's own text where 1.0 kept the English.
    native_dir = os.path.join(SPT_DB, "locales", "global")
    native = {}
    for code in sorted(translations.LANGS | {"en"}):
        path = os.path.join(native_dir, f"{code}.json")
        if os.path.exists(path):
            native[code] = json.load(open(path, encoding="utf-8"))
    # the 1.0 game's own translations of quest names and objectives, from tarkov.dev
    live = {code: translations.live(DATA, code, TEXT) for code in translations.LANGS}
    report["live_translations"] = {}

    def write_locales(base, english, count=False):
        os.makedirs(os.path.join(base, "Locales"), exist_ok=True)
        json.dump(english, open(os.path.join(base, "Locales", "en.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
        for code in sorted(set(translated) | (set(native) - {"en"})):
            tr, lv = translated.get(code, {}), live.get(code, {})
            loc = translations.localize(english, tr, native.get(code), native.get("en"), lv, TEXT)
            json.dump(loc, open(os.path.join(base, "Locales", f"{code}.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
            if not count:
                continue
            if code in translated:
                done = report["translations"].setdefault(code, [0, 0])
                done[0] += sum(1 for k, v in english.items() if v and k in tr)
                done[1] += sum(1 for v in english.values() if v)
            used = sum(1 for k, v in english.items() if v and k not in tr and lv.get(k) and TEXT.get(k) == v)
            if used:
                report["live_translations"][code] = report["live_translations"].get(code, 0) + used

    for trader, quests in by_trader.items():
        base = os.path.join(db, "CustomQuests", trader)
        os.makedirs(os.path.join(base, "Quests"), exist_ok=True)
        json.dump(quests, open(os.path.join(base, "Quests", "quests.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
        write_locales(base, locales[trader], count=True)
        if icons_used.get(trader):
            os.makedirs(os.path.join(base, "Images"), exist_ok=True)
            for icon in icons_used[trader]:
                shutil.copy(icon, os.path.join(base, "Images", os.path.basename(icon)))
        if trader in quest_assort:
            os.makedirs(os.path.join(base, "QuestAssort"), exist_ok=True)
            json.dump(quest_assort[trader], open(os.path.join(base, "QuestAssort", "assort.json"), "w"), indent=1)

    # SPT's own quests too: 1.0 split chains like Vitamins/Supplements by faction, and their 1.0 unlocks
    # no longer go through the other side's quest. One SPT had for both sides stays that way when a quest
    # for both sides needs it (Perfect Mediator needs Shaking Up the Teller), or the other side loses that one
    needed = {r["task"] if isinstance(r["task"], str) else r["task"]["id"]
              for t in tasks if t.get("factionName") == "Any" for r in t.get("taskRequirements") or []}
    side = {"usecOnlyQuests": [], "bearOnlyQuests": []}
    for t in tasks:
        faction = t.get("factionName")
        if faction not in ("USEC", "BEAR") or t["id"] in SKIP:
            continue
        if t["id"] in ctx.quests and t["id"] in needed:
            ctx.warn(t["id"], f"{name_of(t['id'])} stays for both sides, a quest for both sides needs it")
            continue
        side[f"{faction.lower()}OnlyQuests"].append(t["id"])
    json.dump(side, open(os.path.join(db, "CustomQuests", "QuestSideData.json"), "w"), indent=1)
    write_tiers(db, by_trader)

    shutil.rmtree(os.path.join(db, "CustomAssortSchemes"), ignore_errors=True)
    if new_assorts:
        os.makedirs(os.path.join(db, "CustomAssortSchemes"), exist_ok=True)
        json.dump(new_assorts, open(os.path.join(db, "CustomAssortSchemes", "assort.json"), "w"), indent=1)

    if zones_out:
        os.makedirs(os.path.join(db, "CustomQuestZones"), exist_ok=True)
        json.dump(zones_out, open(os.path.join(db, "CustomQuestZones", "zones.json"), "w"), indent=1)
    if spawns_out:
        os.makedirs(os.path.join(db, "CustomLootspawns", "CustomSpawnpointsForced"), exist_ok=True)
        json.dump(spawns_out, open(os.path.join(db, "CustomLootspawns", "CustomSpawnpointsForced", "forced.json"), "w"), indent=1)

    build_optional(db, write_locales)

    report["warnings"] = ctx.warnings
    json.dump(report, open(os.path.join(OUT, "build_report.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(f"new quests: {len(report['new'])}  patched quests: {len(report['patched'])}  skipped: {len(report['skipped'])}")
    print(f"custom zones: {report['zones']}  forced spawns: {report['spawns']}  warnings: {len(ctx.warnings)}")
    print(f"quests unlocked by quests done at a loyalty level: {report['tiers']}")
    for code, (done, total) in report["translations"].items():
        print(f"translation {code}: {done}/{total}")
    if report["live_translations"]:
        print("1.0 translations from tarkov.dev: " + "  ".join(f"{c} {n}" for c, n in sorted(report["live_translations"].items())))
    else:
        print("no 1.0 translations in the data folder, run fetch_data.py to get them")


main()
