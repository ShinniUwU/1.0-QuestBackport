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

## Building

See the Building section in the README. You'll need Python 3.10+, the .NET 10 SDK and an SPT 4.1 install with WTT-ContentBackport. The scripts are written for Windows. I haven't tried them on Linux yet.

`tools/calibrate.py` converts quests SPT already has and diffs them against SPT's own JSON. If you change `tools/convert.py`, run it to check you didn't break anything.

## Pull requests

- One fix per PR if you can
- Say which quests you tested and on what SPT version
- Don't commit anything from `dist/` or the tarkov.dev downloads in `data/` (the gitignore already skips them)

Contributors get credited in the release notes.
