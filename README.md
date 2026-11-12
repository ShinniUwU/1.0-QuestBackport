# Shinni's 1.0 QuestsBackport

Server mod for SPT 4.1.x that brings the quests up to Escape from Tarkov 1.0 (PvE).

Download it on the [Forge](https://sp-mod.com/mod/3340/shinnis-10-questsbackport).

- Adds the 32 quests from 1.0 that SPT doesn't have, with their 1.0 briefings, icons, level requirements and rewards.
- Updates 391 existing quests to their 1.0 versions: counts, levels, maps, weapons, XP, money, item rewards, added and removed objectives. Quest ids don't change, so quests already in progress keep their progress.

## Requirements

Server:
- SPT 4.1.x
- [WTT-ServerCommonLib](https://github.com/WelcomeToThursday/WTT-CommonLib) 3.x
- WTT-ContentBackport (server part). Many 1.0 quest items, weapons and rewards come from it.

Every player (and a Fika headless client):
- WTT-ClientCommonLib. It builds the new quest zones.
- WTT-ContentBackport (client part) for the 1.0 item models.

## Install

Open the release zip and drag its `SPT_Runtime` folder into your SPT folder (the one with `EscapeFromTarkov.exe`). Restart the server.

Only the server needs this mod. Players joining a server don't install it.

On startup the server log should show:

```
[Shinni's 1.0 QuestsBackport] 423/423 backported quests in the database
```

## Compatibility

- **RefFriendlyQuests** (acidphantasm): compatible. The 6 Ref quests it rewrites are skipped, and this mod loads before it, so its versions win.
- **viper's Quest Backport**: don't run both. They change the same quests.

## Stand-ins

The 0.16.9 client SPT is built on is missing some 1.0 content, so a few objectives use the closest thing that exists:

| 1.0 | Here |
|---|---|
| Icebreaker map | Lighthouse, using zones and spawn points that already exist there |
| Arena "win a match" | Survive and extract |
| Talk to the BTR driver | Extract on Streets of Tarkov |
| The Wedge's squad and trophy | The Goons, and Knight's Death Knight mask |
| Lab (dark), Infected Factory, Ground Zero tutorial | Lab, Factory, Ground Zero |

Trader offers that new quests unlock are added to trader stock behind the quest, at 1.0 prices.

## What it leaves alone

- **Trader standing.** 1.0 rescaled trader loyalty about 10x. Standing rewards on existing quests keep SPT's values, and new quests get the 1.0 value scaled to SPT's thresholds.
- **Craft and trader unlock rewards on existing quests.** Removing them can lock a hideout recipe or trader item for good.
- **Quests 1.0 removed.** They stay in the game.

## Building

Needs Python 3.10+, .NET 10 SDK and an SPT 4.1 install with WTT-ContentBackport (the build reads its database and DLLs).

```
python tools/fetch_data.py data C:\SPT\SPT_Runtime
python tools/fetch_wiki.py data C:\SPT\SPT_Runtime\SPT_Data\database
powershell -File tools/fetch_icons.ps1 data C:\SPT\SPT_Runtime\SPT_Data\database
powershell -File tools/package.ps1 -Spt C:\SPT\SPT_Runtime
```

The zip lands in `dist/`, with `dist/build_report.json` listing every new and changed quest.

- `tools/convert.py` turns tarkov.dev objectives into BSG quest conditions.
- `tools/build.py` builds the new quests and patches existing ones.
- `tools/overrides.json` holds the hand-made stand-ins.
- `tools/calibrate.py` converts quests SPT already has and diffs them against SPT's JSON, to catch converter bugs.

## Contributing

To report a broken quest or help out, see [CONTRIBUTING.md](CONTRIBUTING.md). Most quest fixes only need a small edit to `tools/overrides.json`.

## Credits

- Quest data: [tarkov.dev](https://tarkov.dev) (json.tarkov.dev).
- Briefing text: [Escape from Tarkov Wiki](https://escapefromtarkov.fandom.com), CC BY-SA 3.0.
- Quest icons: Battlestate Games.
- Quest, zone, loot and trader loading: [WTT-CommonLib](https://github.com/WelcomeToThursday/WTT-CommonLib).
