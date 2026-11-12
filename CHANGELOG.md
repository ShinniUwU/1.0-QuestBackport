# Changelog

## 0.2.0-alpha.1 (testing, not on the Forge yet)

- Update notice: logs a warning and messages players in game when a newer version is on the Forge. Both can be turned off in the new `config.json`
- Translations: quest text can be translated in a spreadsheet (`translations/<code>.csv`), anything untranslated falls back to English
- Quests the mod only updates now keep the game's own text in other languages where 1.0 didn't change it, instead of switching to English
- Builds on Linux and macOS with `tools/package.py`, and the C# part no longer needs an SPT install to compile

## 0.1.0 (2026-11-12)

First release.

- Adds the 32 quests from 1.0 that SPT 4.1 doesn't have
- Updates 391 existing quests to their 1.0 versions
- Adds the trader offers new quests unlock, at 1.0 prices
- Stand-ins for 1.0 content the 0.16.9 client lacks (Icebreaker on Lighthouse, The Goons for The Wedge, and a few others, see the README)
