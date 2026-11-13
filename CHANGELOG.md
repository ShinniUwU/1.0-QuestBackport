# Changelog

## 0.3.0 (2026-11-13)

- Update notice: logs a warning and messages players in game when a newer version is on the Forge. Both can be turned off in the new `config.json`
- Quest names and objectives now use the 1.0 game's own translations in every language SPT has. Russian, Chinese, Spanish, Italian and Portuguese are almost complete. Briefings of the 32 new quests and the stand-in objectives stay English
- Translations: quest text can be translated in a spreadsheet (`translations/<code>.csv`), anything untranslated falls back to English
- Quests the mod only updates now keep the game's own text in other languages where 1.0 didn't change it, instead of switching to English
- Builds on Linux and macOS with `tools/package.py`, and the C# part no longer needs an SPT install to compile

## 0.2.0 (2026-11-13)

- A Wedge Between Us uses the real Wedge when Black Division or the Wedge mod is installed
- With Manimal's Icebreaker Backport installed, its Icebreaker quests replace the Lighthouse stand-ins
- Fixes 8 new quests being available on a fresh profile: Special Order, Goals and Means, Secret Message, Invasive Therapy, Stimulating Demand, Akimbo and Sisyphus now wait for their trader loyalty level, Compensation for Damage - Wergild for low Fence standing

## 0.1.1 (2026-11-13)

- Fixes Reconnaissance, No Swiping, The Huntsman Path - Trophy and Payback showing no objectives and missing from the Tasks list

## 0.1.0 (2026-11-12)

First release.

- Adds the 32 quests from 1.0 that SPT 4.1 doesn't have
- Updates 391 existing quests to their 1.0 versions
- Adds the trader offers new quests unlock, at 1.0 prices
- Stand-ins for 1.0 content the 0.16.9 client lacks (Icebreaker on Lighthouse, The Goons for The Wedge, and a few others, see the README)
