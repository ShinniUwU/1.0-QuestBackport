# Changelog

## 0.4.5 (2026-11-27)

- Fixes Steady Signal and Abandoned Cargo only taking the marker at one spot (weather station 1, the cargo box in the red warehouse). 1.0 merged "mark the first/second/..." into one "mark any", and the old client takes one zone per objective. The mod now adds its own zone at every spot, so any weather station or cargo box works
- Same fix for Black Swan, Revision - Lighthouse, Oil Run, Tigr Safari and Fuel Crisis
- Optional 1.0 objectives SPT doesn't have are left out instead of becoming required, since the client has no optional objectives. 23 objectives in 11 quests, like Abandoned Cargo's "Locate the cargo" ones and Supervisor's extra register keys

## 0.4.4 (2026-11-25)

- Fixes the Mk-18 at Jaeger LL4 unlocking from an LL1 quest. 1.0 turned Hunter into All This Filth..., a 20 Scav quest Jaeger gives at LL1, but it kept SPT's old reward for killing Shturman. The offer now unlocks with The Tarkov Shooter - Part 7 like in 1.0 (SPT's Part 8)
- If you finished the old Hunter but not The Tarkov Shooter - Part 7 yet, the Mk-18 offer is locked again until you do

## 0.4.3 (2026-11-25)

- Fixes Consolation Prize showing up as soon as Skier is unlocked. SPT only gated it behind A Life Lesson, 1.0 dropped that for level 46, and 0.4.0 took the drop but not the level. It now waits for level 46
- Same fix for Test Drive - Part 3 (level 25), Test Drive - Part 6 (level 35) and Keeper's Word (level 26). 105 quests in total get their 1.0 level requirement back, the rest were still gated by their prerequisite quest
- The server log now counts 455 quests

## 0.4.2 (2026-11-25)

- Fixes Jaeger's boss quests showing up right after unlocking Jaeger. tarkov.dev has no unlock data for 14 quests, so 0.4.0 opened them at LL1. They now wait like in 1.0: Sellout, Factory Chief and Crooked Cop for Jaeger LL2, Big Game for 2 Jaeger quests done at LL2
- Same fix for Capturing Outposts, You've Got Mail, Green Corridor, Gendarmerie - District Patrol, Possessor (Prapor LL2), The Punisher - Part 3 (1 Prapor quest done at LL2), A Helping Hand (Mechanic LL2) and Health Care Privacy - Part 1 (3 Therapist quests done at LL1)
- Information Source waits for Getting Acquainted again and Provide Viewership for Easy Money - Part 2
- The server log now says 171 quests unlock once enough quests are done at a loyalty level

## 0.4.1 (2026-11-25)

- Fixes BEARs getting USEC quests and the other way round (19 quests: Supplements and Vitamins from Skier, the faction Gunsmith parts, Oil Run, Inventory Files, A Big Loss, Debtor and more). 1.0 split these by faction and 0.4.0 took their 1.0 unlocks, but only marked new quests as faction-only. Shaking Up the Teller and House Arrest stay open to both sides, since Perfect Mediator and House Arrest - Part 2 need them
- Fixes The Punisher - Part 1 showing up as new for players already on Part 3. 1.0 reordered the chain (its Part 1 is SPT's old Part 3), so it now waits for the old Part 2 on profiles that started the chain the old way. New profiles get 1.0's order. Sew it Good - Part 2, Gunsmith Master - Part 1, A Life Lesson and The Survivalist Path - Thrifty were reordered too and work the same way

## 0.4.0 (2026-11-24)

- Fixes quests still asking for the old weapon parts. Getting Some Air wanted the 1P78-1 scope instead of the EKP-1S-03, Power of Persuasion and Easy-Breezy wanted SR-2M and UZI PRO parts so the 1.0 weapon never counted, and Wet Job - Part 1 and The Punisher - Part 3 still wanted a suppressor
- Fixes weapon lists that kept the old weapons next to the 1.0 ones. One-Way Ticket and The Punisher - Part 4 still took 12ga shotguns. The Punisher - Part 3 and 5 and Our Own Land now ask for their 1.0 weapons, The Good Times - Part 1 and Claustrophobia no longer ask for one
- Fixes kill distance limits 1.0 removed: The Tarkov Shooter - Part 4 and 6, The Tarkov Import, Best Job in the World and Connections Up North
- Fixes Gunsmith specs on 21 quests. Gunsmith Master - Part 4 wanted ergonomics 70 and recoil 250 instead of 53 and 300. Every one of them got easier
- Fixes gear requirements. The Punisher - Part 4 no longer wants a balaclava, The Punisher - Part 5 no longer wants PACA and a 6B47, and Setting Priorities asked for all 17 headsets at once so it couldn't be done
- Fixes The Huntsman Path - Administrator still pointing at the Pinewood hotel on Streets. It's at the Reserve train depot like 1.0. Capturing Outposts, Long Road, Pest Control, Provocation, No Swiping and Reconnaissance get their 1.0 spots too, and 6 kill objectives 1.0 opened up to the whole map no longer need a zone
- Kill objectives only count on the maps their 1.0 text names (Debut, Stirrup, The Huntsman Path - Forest Cleaning and more). Unprotected but Dangerous works on any map and also bans plate carriers
- Sew it Good - Part 3 and 4 no longer want armor in a durability range, Trophies takes level 20+ dog tags, and objectives that say "in one raid" in 1.0 are one raid here too (Administrator, Stray Dogs, Payback)
- Quests that moved show up under their 1.0 map, and the selling quests (Building Foundations, Circulate) also take 1.0's new items
- Fixes the Russian briefing of A Wedge Between Us and the reward text of Can't Drink Away Skill showing the wrong text. A quote in the English text broke the spreadsheet row
- Existing quests unlock like 1.0: their prerequisite quests, trader loyalty and Fence standing gates and unlock delays come from 1.0. Aid Stations now waits for Therapist LL2 instead of Out of Curiosity, Collector wants LL4 with every trader and Fence standing 3, and the Gunsmith Master quests lose their 21 hour wait
- 168 quests that 1.0 unlocks once you've done enough quests for a trader at a loyalty level ("finish 3 Prapor quests at LL1") now work that way. The server counts it, so it needs nothing on the client. New quests like Hiking and Fall Ailment were available from the start before
- The server log now counts 443 quests

## 0.3.3 (2026-11-17)

- Fixes completing Special Order, Setting Priorities, Goals and Means and The Huntsman Path - Control. Their skill reward had no skill set, so the server threw `Value cannot be null` and gave no rewards
- Fixes Golden Swag asking you to stash the Zibbo in the old portable cabin. It now uses Dorm room 303 like 1.0. Bullshit's stash spots move to the 1.0 spot too

## 0.3.2 (2026-11-13)

- Fixes start items on 34 existing quests not matching 1.0. Fishing Gear handed out an SV-98 while the objective asked for an MF-UNTAR body armor
- Fixes 4 stash objectives that still wanted the old item: Fishing Gear, Golden Swag and two in Bullshit
- Balancing - Part 1 [PVE ZONE] is now updated too, so the server log counts 424 quests

## 0.3.1 (2026-11-13)

- Russian is now complete: trader briefings of the 32 new quests and the stand-in objectives, translated by [hekawa](https://sp-mod.com/user/56165/hekawa)
- Removed the optional support for Wedge (Sipto). That mod only runs on SPT 4.0.13 and this one needs 4.1, so the two could never load together. Black Division still swaps in the real Wedge

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
