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
from convert import MAP_SUBSTITUTES, STATUS, Ctx, convert_objective, mongo_id  # noqa: E402
import translations  # noqa: E402

DATA, SPT_DB, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
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
        skill = s.get("skill", {}).get("id") if isinstance(s.get("skill"), dict) else s.get("name")
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


def objectives_for(t, locale):
    conds = []
    for i, o in enumerate(t["objectives"]):
        if o["id"] in OVERRIDES.get("drop", []):
            continue
        o = dict(o)
        o.update(OVERRIDES.get("objectives", {}).get(o["id"], {}))
        text = TEXT.get(o["id"]) or ""
        o, new_text = substitute(o, t["id"], text)
        if o is None:
            continue
        o["_oneSession"] = one_session(text)
        d = distance_from(text)
        if o["type"] == "shoot" and d and not (o.get("distance") or {}).get("value"):
            o["distance"] = {"compareMethod": ">=", "value": d}
        ensure_zones(o)
        ensure_spawns(o, t["id"])
        c = convert_objective(o, t["id"], ctx, len(conds))
        if c is None:
            ctx.warn(t["id"], f"objective {o['id']} type {o['type']} not convertible, dropped")
            continue
        conds.append(c)
        locale[o["id"]] = OVERRIDES.get("text", {}).get(o["id"]) or _map_name_text(new_text or text)
    return conds


# ---------------------------------------------------------------- quests

QUEST_TYPE = {"shoot": "Elimination", "giveItem": "PickUp", "findItem": "PickUp", "visit": "Exploration", "extract": "Exploration",
              "plantItem": "Completion", "mark": "Completion", "buildWeapon": "WeaponAssembly", "skill": "Skill"}


def start_conditions(t):
    out = []
    if t.get("minPlayerLevel"):
        out.append({"compareMethod": ">=", "conditionType": "Level", "dynamicLocale": False, "globalQuestCounterId": "",
                    "id": mongo_id(t["id"], "level"), "index": 0, "parentId": "", "value": t["minPlayerLevel"], "visibilityConditions": []})
    for r in t.get("taskRequirements") or []:
        target = r["task"] if isinstance(r["task"], str) else r["task"]["id"]
        if target in SKIP or (target not in ctx.quests and target not in TASK_IDS):
            ctx.warn(t["id"], f"prerequisite {target} not available, dropped")
            continue
        out.append({"availableAfter": 0, "conditionType": "Quest", "dispersion": 0, "dynamicLocale": False, "globalQuestCounterId": "",
                    "id": mongo_id(t["id"], "req", target), "index": len(out), "parentId": "",
                    "status": sorted({STATUS[s] for s in r.get("status") or ["complete"]}), "target": target, "visibilityConditions": []})
    for r in t.get("traderRequirements") or []:
        if r.get("requirementType") == "level":
            out.append({"compareMethod": r.get("compareMethod", ">="), "conditionType": "TraderLoyalty", "dynamicLocale": False,
                        "globalQuestCounterId": "", "id": r.get("id") or mongo_id(t["id"], "loyalty"), "index": len(out), "parentId": "",
                        "target": r["trader"], "value": r["value"], "visibilityConditions": []})
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


def new_quest(t):
    qid = t["id"]
    locale = {}
    conds = objectives_for(t, locale)
    fail = []
    for i, o in enumerate(t.get("failConditions") or []):
        o, _ = substitute(dict(o), qid, TEXT.get(o["id"]) or "")
        if o is None or (o["type"] == "extract" and not o.get("maps")):
            continue  # Arena match-loss fail conditions have no raid equivalent
        c = convert_objective(o, qid, ctx, len(fail))
        if c:
            fail.append(c)
            locale[o["id"]] = TEXT.get(o["id"]) or ""
    loc = ctx.map_id(t["map"]) if t.get("map") else "any"
    if loc != "any" and loc not in ctx.loc_by_mongo:
        loc = "any"
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
    locale = {}
    td_ids = set()
    for i, o in enumerate(t["objectives"]):
        td_ids.add(o["id"])
        text = TEXT.get(o["id"]) or ""
        old = by_id.get(o["id"])
        if old is None:
            o2, new_text = substitute(dict(o), qid, text)
            if o2 is None:
                continue
            o2["_oneSession"] = one_session(text)
            ensure_zones(o2)
            ensure_spawns(o2, qid)
            c = convert_objective(o2, qid, ctx, len(q["conditions"]["AvailableForFinish"]))
            if c:
                q["conditions"]["AvailableForFinish"].append(c)
                locale[o["id"]] = _map_name_text(new_text or text)
                changes.append(f"+objective {o['type']}")
            continue
        new = convert_objective({**o, "_oneSession": old.get("oneSessionOnly", False)}, qid, ctx, old.get("index", i))
        if new is None:
            continue
        if new.get("value") is not None and old.get("value") != new["value"]:
            changes.append(f"{o['type']} count {old.get('value')}->{new['value']}")
            old["value"] = new["value"]
        if old["conditionType"] in ("HandoverItem", "FindItem") and new["conditionType"] == old["conditionType"]:
            tgt = ctx.known(new["target"])
            if tgt and sorted(tgt) != sorted(old["target"]):
                changes.append(f"{o['type']} items changed")
                old["target"] = tgt
            if old.get("onlyFoundInRaid") != new.get("onlyFoundInRaid"):
                changes.append(f"FIR {old.get('onlyFoundInRaid')}->{new.get('onlyFoundInRaid')}")
                old["onlyFoundInRaid"] = new["onlyFoundInRaid"]
        if old["conditionType"] == "CounterCreator" and new["conditionType"] == "CounterCreator":
            _patch_counter(old, new, o, changes, text)
        if text:
            locale[o["id"]] = text
    # objectives 1.0 removed
    if td_ids:
        keep = [c for c in q["conditions"]["AvailableForFinish"] if c["id"] in td_ids or c["id"] in {x for x in locale}]
        removed = len(q["conditions"]["AvailableForFinish"]) - len(keep)
        if removed:
            changes.append(f"-{removed} objective(s)")
            q["conditions"]["AvailableForFinish"] = keep
    _patch_rewards(q, t, changes)
    if t.get("name") and TEXT.get(f"{qid} name"):
        locale[f"{qid} name"] = TEXT[f"{qid} name"]
    return q, locale, changes


def _patch_counter(old, new, o, changes, text=""):
    olds = {sc["conditionType"]: sc for sc in old["counter"]["conditions"]}
    for sc in new["counter"]["conditions"]:
        prev = olds.get(sc["conditionType"])
        if prev is None:
            continue
        if sc["conditionType"] == "Location" and sorted(prev["target"]) != sorted(sc["target"]):
            changes.append(f"map {prev['target']}->{sc['target']}")
            prev["target"] = sc["target"]
        if sc["conditionType"] in ("Kills", "Shots"):
            # union, so weapons other mods add (RefFriendlyQuests, WTT) survive
            merged = list(dict.fromkeys((prev.get("weapon") or []) + sc["weapon"]))
            if prev.get("weapon") and len(merged) != len(prev["weapon"]):
                changes.append("weapon list updated")
                prev["weapon"] = merged
            if sorted(sc["bodyPart"]) != sorted(prev.get("bodyPart") or []):
                changes.append(f"body parts {prev.get('bodyPart')}->{sc['bodyPart']}")
                prev["bodyPart"] = sc["bodyPart"]
            if sc["distance"]["value"] and sc["distance"] != prev.get("distance"):
                changes.append(f"distance ->{sc['distance']['value']}")
                prev["distance"] = sc["distance"]
            # tarkov.dev collapses some targets to "Any"; only trust specific ones
            # tarkov.dev reports both "any target" and some specific kills as "Any";
            # only trust "Any" when the 1.0 objective text says so too.
            trusted = sc["target"] != "Any" or "any target" in text.lower()
            if trusted and (sc["target"], sc["savageRole"]) != (prev.get("target"), prev.get("savageRole")):
                changes.append(f"target {prev.get('target')}{prev.get('savageRole') or ''}->{sc['target']}{sc['savageRole'] or ''}")
                prev["target"], prev["savageRole"] = sc["target"], sc["savageRole"]


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
    # Standing is left alone: 1.0 rescaled trader loyalty ~10x, SPT still uses the old scale.


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

    for trader, quests in by_trader.items():
        base = os.path.join(db, "CustomQuests", trader)
        os.makedirs(os.path.join(base, "Quests"), exist_ok=True)
        os.makedirs(os.path.join(base, "Locales"), exist_ok=True)
        json.dump(quests, open(os.path.join(base, "Quests", "quests.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
        json.dump(locales[trader], open(os.path.join(base, "Locales", "en.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
        for code in sorted(set(translated) | (set(native) - {"en"})):
            tr = translated.get(code, {})
            loc = translations.localize(locales[trader], tr, native.get(code), native.get("en"))
            json.dump(loc, open(os.path.join(base, "Locales", f"{code}.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
            if code in translated:
                done = report["translations"].setdefault(code, [0, 0])
                done[0] += sum(1 for k, v in locales[trader].items() if v and k in tr)
                done[1] += sum(1 for v in locales[trader].values() if v)
        if icons_used.get(trader):
            os.makedirs(os.path.join(base, "Images"), exist_ok=True)
            for icon in icons_used[trader]:
                shutil.copy(icon, os.path.join(base, "Images", os.path.basename(icon)))
        if trader in quest_assort:
            os.makedirs(os.path.join(base, "QuestAssort"), exist_ok=True)
            json.dump(quest_assort[trader], open(os.path.join(base, "QuestAssort", "assort.json"), "w"), indent=1)

    side = {"usecOnlyQuests": [t["id"] for t in tasks if t.get("factionName") == "USEC" and t["id"] not in ctx.quests and t["id"] not in SKIP],
            "bearOnlyQuests": [t["id"] for t in tasks if t.get("factionName") == "BEAR" and t["id"] not in ctx.quests and t["id"] not in SKIP]}
    json.dump(side, open(os.path.join(db, "CustomQuests", "QuestSideData.json"), "w"), indent=1)

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

    report["warnings"] = ctx.warnings
    json.dump(report, open(os.path.join(OUT, "build_report.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(f"new quests: {len(report['new'])}  patched quests: {len(report['patched'])}  skipped: {len(report['skipped'])}")
    print(f"custom zones: {report['zones']}  forced spawns: {report['spawns']}  warnings: {len(ctx.warnings)}")
    for code, (done, total) in report["translations"].items():
        print(f"translation {code}: {done}/{total}")


main()
