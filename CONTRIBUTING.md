# Contributing

If you want to help but don't know where to start, look at the issues tagged [good first issue](https://github.com/ShinniUwU/1.0-QuestBackport/labels/good%20first%20issue).

## Reporting a broken quest

Use the "Broken quest" issue form. The quest name, SPT version, the `[Shinni's 1.0 QuestsBackport]` log line and your other quest/trader/map mods are usually enough for me to reproduce it.

## Fixing a quest without touching the code

Most fixes go in `tools/overrides.json`, which is plain JSON keyed by objective id:

- `objectives`: fields to replace on an objective, like `maps`, `zones`, `count` or `targetNames`
- `drop`: objective ids to leave out
- `text`: replacement objective text

To find an objective id, run a build and look in `dist/build_report.json`, or grab it from the quest's page on tarkov.dev.

Example, moving an objective to Lighthouse:

```json
"69e5593e3f425636f1d762d9": {
  "zones": [{ "id": "w_race_cam1", "map": "5704e4dad2720bb55b8b4567" }],
  "maps": ["5704e4dad2720bb55b8b4567"]
}
```

If you can't build it yourself, open a PR with just the JSON change and say what it fixes. I'll build and test it.

## Translating

You only need a spreadsheet program (Excel, LibreOffice or Google Sheets).

1. Download [`translations/en.csv`](translations/en.csv)
2. Save a copy named after your language's SPT code: `ru` Russian, `kr` Korean, `ch` Chinese, `jp` Japanese, `ge` German, `fr` French, `es` Spanish, `es-mx` Spanish (Mexico), `it` Italian, `pl` Polish, `po` Portuguese, `cz` Czech, `sk` Slovak, `hu` Hungarian, `ro` Romanian, `tu` Turkish. For example `ru.csv`
3. Fill in the `translation` column. Leave the `id` and `english` columns as they are
4. Save it as CSV (UTF-8) and open a PR adding it to `translations/`, or attach it to the [translations issue](https://github.com/ShinniUwU/1.0-QuestBackport/issues/2) if you don't use git

You don't have to finish it. Empty rows show up in English, and quests the mod only updates keep the game's own text in your language where 1.0 didn't change it.

When new quests come out, `python tools/translations.py` adds their rows to every language file and keeps what's already translated.

## Building

See the Building section in the README. You'll need Python 3.10+ and the .NET 10 SDK. The C# part builds without SPT (it pulls SPT and WTT from NuGet), but generating the quests needs an SPT 4.1 install with WTT-ContentBackport. `tools/package.py` only needs Python and dotnet, so it's meant to run on Windows, Linux and macOS (if it breaks on yours, open an issue). The only Windows-only script is `fetch_icons.ps1`, and you won't need it unless you're adding icons for new quests.

`tools/calibrate.py` converts quests SPT already has and diffs them against SPT's own JSON. If you change `tools/convert.py`, run it to check you didn't break anything.

## Pull requests

- One fix per PR if you can
- Say which quests you tested and on what SPT version
- Don't commit anything from `dist/` or the tarkov.dev downloads in `data/` (the gitignore already skips them)

Contributors get credited in the release notes.
