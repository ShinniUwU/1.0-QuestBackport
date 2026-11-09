"""Convert tarkov.dev task data into BSG/SPT quest JSON.

tarkov.dev keeps BSG's quest and objective ids but drops internal sub-ids
(counter ids, reward ids, subcondition ids). Missing ids are generated
deterministically from a seed so rebuilding gives the same output.
"""
import hashlib
import json
import os

GAME_MODES = ["regular", "pve"]

# Maps that exist in 1.0 but not in SPT 0.16.9, and what to use instead.
MAP_SUBSTITUTES = {
    "6a294a5b5eb5f9a1700417b7": "5b0fc42d86f7744a585f9105",  # Lab (dark) -> Lab
    "6a8dd1325e15a5ea2e010820": "55f2d3fd4bdc2d5f408b4567",  # Infected Factory -> Factory
    "68236e8153654e8c1200798a": "653e6760052c01c1c805532f",  # Ground Zero tutorial -> Ground Zero
    "69af492a4819ea4ba10a69c5": "5704e4dad2720bb55b8b4567",  # Icebreaker -> Lighthouse
}

PMC_TARGETS = {"Any", "AnyPmc", "Bear", "Usec", "Savage"}
SCAV_EXPANSION = {"Savage", "assaultGroup", "Marksman"}


def mongo_id(*seed):
    """Deterministic 24-hex id that looks like a BSG id."""
    h = hashlib.sha1("|".join(map(str, seed)).encode()).hexdigest()
    return h[:24]


class Ctx:
    def __init__(self, spt_db, wtt_ids):
        self.db = spt_db
        self.quests = json.load(open(f"{spt_db}/templates/quests.json", encoding="utf-8"))
        self.items = json.load(open(f"{spt_db}/templates/items.json", encoding="utf-8"))
        self.globals = json.load(open(f"{spt_db}/globals.json", encoding="utf-8"))
        self.presets = self.globals["ItemPresets"]
        self.known_items = set(self.items) | set(wtt_ids)
        self.loc_by_mongo = {}
        for name in os.listdir(f"{spt_db}/locations"):
            p = f"{spt_db}/locations/{name}/base.json"
            if os.path.exists(p):
                b = json.load(open(p, encoding="utf-8"))
                self.loc_by_mongo[b["_Id"]] = b["Id"]
        self.bot_roles = {f[:-5] for f in os.listdir(f"{spt_db}/bots/types") if f.endswith(".json")}
        self.all_locations = set(self.loc_by_mongo.values()) - {"develop", "hideout", "Private Area", "Suburbs", "Terminal", "Town"}
        self.text = {}  # objective id -> english text, filled by the caller
        self.warnings = []

    def warn(self, qid, msg):
        self.warnings.append(f"{qid}: {msg}")

    def map_id(self, m):
        return MAP_SUBSTITUTES.get(m, m)

    def location_names(self, maps):
        out = []
        for m in maps or []:
            name = self.loc_by_mongo.get(self.map_id(m))
            if name and name not in out:
                out.append(name)
        return out

    def known(self, ids):
        """Drop item ids neither SPT nor WTT-ContentBackport knows."""
        return [i for i in ids if i in self.known_items]


def _cmp(v):
    return {"compareMethod": (v or {}).get("compareMethod", ">="), "value": (v or {}).get("value", 0)}


def _body_parts(parts):
    return [p.rsplit("/", 1)[-1] for p in parts or []]


def _role(name):
    # tarkov.dev capitalises some roles (Marksman, PmcBot, ExUsec); BSG uses camelCase.
    return name[0].lower() + name[1:]


# Objective text tells us the target when tarkov.dev collapsed it to "Any".
TEXT_TARGETS = [
    ("raiders", ("Savage", ["pmcBot"])),
    ("rogues", ("Savage", ["exUsec"])),
    ("pmc operatives", ("AnyPmc", [])),
    ("usec", ("Usec", [])),
    ("bear", ("Bear", [])),
    ("scavs", ("Savage", [])),
    ("any target", ("Any", [])),
    ("enemies", ("Any", [])),
]


def _kill_target(names, ctx, text=""):
    """tarkov.dev expands targets (Savage -> Savage, assaultGroup, Marksman).
    Fold that back into BSG's target + savageRole."""
    names = list(names or [])
    s = set(names)
    if not s or s == {"Any"}:
        low = text.lower()
        for needle, res in TEXT_TARGETS:
            if needle in low:
                return res[0], list(res[1])
        return "Any", []
    if s <= PMC_TARGETS and len(s) == 1:
        return names[0], []
    if s == SCAV_EXPANSION or s == {"Savage"}:
        return "Savage", []
    if s == {"AnyPmc"} | SCAV_EXPANSION or s == {"Any"} | SCAV_EXPANSION:
        return "Any", []
    roles = []
    for n in names:
        if n in PMC_TARGETS:
            continue
        r = _role(n)
        if r.lower() in ctx.bot_roles and r not in roles:
            roles.append(r)
    return "Savage", roles


def _counter_cond(o, qid, typ, subconds, ctx, index):
    oid = o["id"]
    desc = ""
    return {
        "completeInSeconds": 0,
        "conditionType": "CounterCreator",
        "counter": {"conditions": subconds, "id": mongo_id(qid, oid, "counter")},
        "doNotResetIfCounterCompleted": False,
        "dynamicLocale": False,
        "globalQuestCounterId": "",
        "id": oid,
        "index": index,
        "isNecessary": False,
        "isResetOnConditionFailed": False,
        "oneSessionOnly": o.get("_oneSession", False),
        "parentId": "",
        "type": typ,
        "value": o.get("count") or 1,
        "visibilityConditions": [],
    }


def _location_sub(o, qid, ctx, tag="loc"):
    names = ctx.location_names(o.get("maps"))
    # tarkov.dev lists every map for "on any location"; BSG omits the Location condition.
    if not names or len(set(names) & ctx.all_locations) >= 8:
        return []
    return [{
        "conditionType": "Location",
        "dynamicLocale": False,
        "id": mongo_id(qid, o["id"], tag),
        "target": names,
    }]


def _zone_ids(o):
    ids = []
    for z in o.get("zones") or []:
        if z["id"] not in ids:
            ids.append(z["id"])
    return ids


def _item_cond(o, ctx, ctype, index, target=None):
    c = {
        "conditionType": ctype,
        "dogtagLevel": o.get("dogTagLevel", 0) or 0,
        "dynamicLocale": False,
        "globalQuestCounterId": "",
        "id": o["id"],
        "index": index,
        "isEncoded": False,
        "maxDurability": o.get("maxDurability", 100) if o.get("maxDurability") is not None else 100,
        "minDurability": o.get("minDurability", 0) or 0,
        "onlyFoundInRaid": bool(o.get("foundInRaid", False)),
        "parentId": "",
        "target": target if target is not None else list(o.get("items") or []),
        "value": o.get("count") or 1,
        "visibilityConditions": [],
    }
    if ctype == "FindItem":
        c["countInRaid"] = False
    return c


def convert_objective(o, qid, ctx, index):
    t = o["type"]
    oid = o["id"]

    if t == "giveItem":
        return _item_cond(o, ctx, "HandoverItem", index)
    if t == "findItem":
        return _item_cond(o, ctx, "FindItem", index)
    if t == "sellItem":
        return _item_cond(o, ctx, "SellItemToTrader", index)
    if t in ("findQuestItem", "giveQuestItem"):
        q = o["questItem"]
        q = q if isinstance(q, str) else q["id"]
        c = _item_cond({**o, "foundInRaid": False}, ctx, "FindItem" if t == "findQuestItem" else "HandoverItem", index, [q])
        return c
    if t in ("plantItem", "plantQuestItem"):
        target = o.get("items") or []
        if t == "plantQuestItem":
            q = o["questItem"]
            target = [q if isinstance(q, str) else q["id"]]
        c = _item_cond({**o, "foundInRaid": o.get("foundInRaid", False)}, ctx, "LeaveItemAtLocation", index, list(target))
        zones = _zone_ids(o)
        c["zoneId"] = zones[0] if zones else ""
        c["plantTime"] = o.get("_plantTime", 20 if t == "plantItem" else 5)
        if not zones:
            ctx.warn(qid, f"{oid} plant objective without zone")
        return c
    if t == "mark":
        zones = _zone_ids(o)
        m = o["markerItem"]
        return {
            "conditionType": "PlaceBeacon",
            "dynamicLocale": False,
            "globalQuestCounterId": "",
            "id": oid,
            "index": index,
            "parentId": "",
            "plantTime": 30,
            "target": [m if isinstance(m, str) else m["id"]],
            "value": o.get("count") or 1,
            "visibilityConditions": [],
            "zoneId": zones[0] if zones else "",
        }
    if t == "visit":
        subs = []
        for i, z in enumerate(_zone_ids(o)):
            subs.append({
                "conditionType": "VisitPlace",
                "dynamicLocale": False,
                "id": mongo_id(qid, oid, "visit", i),
                "target": z,
                "value": 1,
            })
        if not subs:
            ctx.warn(qid, f"{oid} visit objective without zone, dropped")
            return None
        return _counter_cond({**o, "count": 1}, qid, "Exploration", subs, ctx, index)
    if t == "extract":
        subs = _location_sub(o, qid, ctx)
        if o.get("exitName"):
            subs.append({
                "conditionType": "ExitName",
                "dynamicLocale": False,
                "exitName": o["exitName"],
                "id": mongo_id(qid, oid, "exitname"),
            })
        status = []
        for s in o.get("exitStatus") or []:
            s = s.replace("ExpBonus", "")
            s = s if s in ("Survived", "Runner") else "Transit"  # "marathon Name" is the transit status
            if s not in status:
                status.append(s)
        subs.append({
            "conditionType": "ExitStatus",
            "dynamicLocale": False,
            "id": mongo_id(qid, oid, "exitstatus"),
            "status": status or ["Survived", "Runner"],
        })
        return _counter_cond(o, qid, "Completion", subs, ctx, index)
    if t == "shoot":
        target, roles = _kill_target(o.get("targetNames"), ctx, ctx.text.get(oid, ""))
        dist = o.get("distance") or {}
        kill = {
            "bodyPart": _body_parts(o.get("bodyParts")),
            "compareMethod": ">=",
            "conditionType": "Kills" if o.get("shotType", "kill") == "kill" else "Shots",
            "daytime": {"from": o.get("timeFromHour") or 0, "to": o.get("timeUntilHour") or 0},
            "distance": {"compareMethod": dist.get("compareMethod", ">="), "value": dist.get("value", 0)},
            "dynamicLocale": False,
            "enemyEquipmentExclusive": [],
            "enemyEquipmentInclusive": [],
            "enemyHealthEffects": [],
            "id": mongo_id(qid, oid, "kill"),
            "resetOnSessionEnd": False,
            "savageRole": roles,
            "target": target,
            "value": 1,
            "weapon": ctx.known(o.get("usingWeapon") or []),
            "weaponCaliber": [],
            "weaponModsExclusive": [],
            "weaponModsInclusive": [g for g in ([ctx.known([m] if isinstance(m, str) else list(m)) for m in o.get("usingWeaponMods") or []]) if g],
        }
        if o.get("usingWeapon") and not kill["weapon"]:
            ctx.warn(qid, f"{oid} every required weapon is unknown to SPT")
        ehe = o.get("enemyHealthEffect")
        if ehe:
            kill["enemyHealthEffects"] = [{
                "bodyParts": _body_parts(ehe.get("bodyParts")),
                "effects": list(ehe.get("effects") or []),
            }]
        subs = []
        phe = o.get("playerHealthEffect")
        if phe:
            subs.append(_health_sub(phe, qid, oid))
        subs.append(kill)
        for i, group in enumerate(o.get("wearing") or []):
            subs.append(_equipment_sub(qid, oid, f"wear{i}", inclusive=[[g["id"] if isinstance(g, dict) else g for g in group]]))
        not_wearing = o.get("notWearing") or []
        if not_wearing:
            subs.append(_equipment_sub(qid, oid, "notwear", exclusive=[[g["id"] if isinstance(g, dict) else g] for g in not_wearing]))
        zones = _zone_ids(o)
        if zones:
            subs.append({
                "conditionType": "InZone",
                "dynamicLocale": False,
                "id": mongo_id(qid, oid, "inzone"),
                "zoneIds": zones,
            })
        subs += _location_sub(o, qid, ctx)
        return _counter_cond(o, qid, "Elimination", subs, ctx, index)
    if t == "experience":
        he = o.get("healthEffect") or {"bodyParts": o.get("bodyParts"), "effects": o.get("effects")}
        subs = [_health_sub(he, qid, oid)] + _location_sub(o, qid, ctx)
        return _counter_cond(o, qid, "Experience", subs, ctx, index)
    if t == "useItem":
        zones = _zone_ids(o)
        if zones:
            subs = [{
                "conditionType": "LaunchFlare",
                "dynamicLocale": False,
                "id": mongo_id(qid, oid, "flare"),
                "target": zones[0],
            }]
        else:
            subs = [{
                "compareMethod": o.get("compareMethod", ">="),
                "conditionType": "UseItem",
                "dynamicLocale": False,
                "id": mongo_id(qid, oid, "useitem"),
                "target": list(o.get("useAny") or []),
                "value": o.get("count") or 1,
            }] + _location_sub(o, qid, ctx)
        return _counter_cond(o, qid, "Completion", subs, ctx, index)
    if t == "taskStatus":
        return {
            "availableAfter": 0,
            "conditionType": "Quest",
            "dispersion": 0,
            "dynamicLocale": False,
            "globalQuestCounterId": "",
            "id": oid,
            "index": index,
            "parentId": "",
            "status": [STATUS[s] for s in o.get("status") or ["complete"]],
            "target": o["task"] if isinstance(o["task"], str) else o["task"]["id"],
            "visibilityConditions": [],
        }
    if t == "traderLevel":
        return {
            "compareMethod": ">=",
            "conditionType": "TraderLoyalty",
            "dynamicLocale": False,
            "globalQuestCounterId": "",
            "id": oid,
            "index": index,
            "parentId": "",
            "target": o["trader"],
            "value": o["level"],
            "visibilityConditions": [],
        }
    if t == "traderStanding":
        return {
            "compareMethod": o.get("compareMethod", ">="),
            "conditionType": "TraderStanding",
            "dynamicLocale": False,
            "globalQuestCounterId": "",
            "id": oid,
            "index": index,
            "parentId": "",
            "target": o["trader"],
            "value": o["value"],
            "visibilityConditions": [],
        }
    if t == "skill":
        skill = o["skill"] if isinstance(o["skill"], str) else o["skill"]["id"]
        return {
            "compareMethod": ">=",
            "conditionType": "Skill",
            "dynamicLocale": False,
            "globalQuestCounterId": "",
            "id": oid,
            "index": index,
            "parentId": "",
            "target": skill,
            "value": o["level"],
            "visibilityConditions": [],
        }
    if t == "buildWeapon":
        a = o.get("buildAttributes") or {}
        return {
            "baseAccuracy": _cmp(a.get("accuracy")),
            "conditionType": "WeaponAssembly",
            "containsItems": list(o.get("containsAll") or []),
            "durability": _cmp(a.get("durability")),
            "dynamicLocale": False,
            "effectiveDistance": _cmp(a.get("effectiveDistance")),
            "emptyTacticalSlot": {"compareMethod": ">=", "value": 0},
            "ergonomics": _cmp(a.get("ergonomics")),
            "globalQuestCounterId": "",
            "hasItemFromCategory": list(o.get("containsCategory") or []),
            "height": _cmp(a.get("height")),
            "id": oid,
            "index": index,
            "magazineCapacity": _cmp(a.get("magazineCapacity")),
            "muzzleVelocity": _cmp(a.get("muzzleVelocity")),
            "parentId": "",
            "recoil": _cmp(a.get("recoil")),
            "target": [o["item"] if isinstance(o["item"], str) else o["item"]["id"]],
            "value": o.get("count") or 1,
            "visibilityConditions": [],
            "weight": _cmp(a.get("weight")),
            "width": _cmp(a.get("width")),
        }
    # dialogue / globalVariable have no SPT equivalent; caller substitutes them.
    return None


STATUS = {"locked": 0, "available": 1, "active": 2, "started": 2, "complete": 4, "completed": 4, "failed": 5}


def _health_sub(he, qid, oid):
    return {
        "bodyPartsWithEffects": [{"bodyParts": _body_parts(he.get("bodyParts")), "effects": list(he.get("effects") or [])}],
        "conditionType": "HealthEffect",
        "dynamicLocale": False,
        "energy": {"compareMethod": ">=", "value": 0},
        "hydration": {"compareMethod": ">=", "value": 0},
        "id": mongo_id(qid, oid, "health"),
        "time": _cmp(he.get("time")),
    }


def _equipment_sub(qid, oid, tag, inclusive=None, exclusive=None):
    return {
        "IncludeNotEquippedItems": False,
        "conditionType": "Equipment",
        "dynamicLocale": False,
        "equipmentExclusive": exclusive or [],
        "equipmentInclusive": inclusive or [],
        "id": mongo_id(qid, oid, tag),
    }
