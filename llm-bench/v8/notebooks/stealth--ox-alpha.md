# stealth/ox-alpha under harness `v8`

This page holds the notes the model kept while it played. A note is whatever the model chose to write down through its `remember` and `revise` tools, so the notebook records what the model thought worth keeping. Some of it was learned in play and some of it the model already knew, and the notebook does not distinguish them.

The route the model planned for each run is on its own page under `plans/`.

## Pass `20260825-175901-dc44`, `--set reasoning=medium`

The pass played 50 runs and averaged 1.12 badges.

### The notebook at the end

1. Kanto map 0 (first map): layer1 catch, layer2 trainers, gym at layer 8 with pokecenter at layer 7. Officer at n2_0 used FIRE Pokemon; Voltorb (Electric) beat it safely. Catches are free bodies — take 2-3 early. Bulbasaur starter is solid.
2. Resist is not immunity: my Lv10 Vulpix (freshly caught, full HP) FAINTED fighting the map 1 Firebreather's Fire Pokemon even though it resists Fire and had STAB. Low level + low bulk loses fights the type chart says are fine. Rule: only send a Pokemon into a fight if its LEVEL is close to the enemy's too, not just its typing. Weakened or underleveled mons sit out; use the healthy counter instead.
3. Wild battles are NOT free XP: seed 10004 map 1, I led a freshly caught Lv4 Krabby (raised to ~Lv7) into a "+1 level" wild fight and it FAINTED (0 HP). Rule: a Pokemon needs to be at/near the enemy's level with decent bulk to survive even a wild node; otherwise lead your strongest healthy mon instead of "leveling up" the weak one. Also: fainted mons stay fainted until a pokecenter — check HP after every fight and route through + before the gym.
4. Trainer fights can still cost real HP even when won: seed 10005 map 1, my Lv13->15 Bulbasaur led into a "Various" Gentleman trainer and came out at 0/38 (fainted). Rule: before ANY fight, check the lead's HP and level vs the tooltip; a neutral matchup at low HP can still faint. Fainted mons stay fainted until a pokecenter — if the only counter is fainted, take a non-battle node or heal first.
5. Wild "+1 level" battles are NOT safe even for a full-HP, on-level lead: seed 10007 map 1, Spearow Lv11 (28/28) led into a +1 wild and came out FAINTED (0/29). Rule: treat every battle node as capable of costing the lead's whole HP bar; only enter one when I can afford to lose that body or have a pokecenter soon. Prefer non-battle nodes when team HP is thin, and never route a fragile mon (low DEF) into wilds just for XP.
6. NO battle node is safe in Kanto maps — only cheaper. Seed 10011 map 3: Ivysaur Lv29 at FULL HP (73/73), resisting both of the Scientist's types (Electric/Poison) with STAB, led into a +2 trainer fight and still FAINTED (0/78). Earlier same run: Poliwag full-HP on-level fainted to a +1 WILD. Rule going forward: before entering ANY battle node, assume the lead may come out at 0 HP. Only enter when (a) I have a pokecenter reachable soon, (b) the lead is expendable or the fight is gym-critical XP, and (c) a healthier backup exists for the next fight. Never route my only counter for an upcoming gym into a filler battle.
7. Kanto map 0: the layer-4 Officer trainer (+2, Fire) cost my Lv7 Bulbasaur its ENTIRE HP bar even with Rocky Helmet — full team HP after every fight cannot be assumed. Rule: after any battle, check team_details; a fainted mon stays fainted until the layer-7 pokecenter. Keep a healthy Water lead (Psyduck beats Fire) in front and treat the starter as fragile until healed.
8. Kanto map 0 recap (seed ~10018): route catch-catch-catch -> wilds -> pokecenter n7_0 -> gym worked; finished map 0 with 3/3 alive and badge 1. Expert Belt on Staryu (Water) was good value. Map 1 layout seen: layer1 catch+wild, layer2 T/i/x, layer5 has T/?/i/$, layer6 i/?/T, layer7 +/?, layer8 gym. Rule that keeps holding: every battle node can cost the lead its whole HP bar even at full HP/on-level — budget one expendable lead per fight and heal at the last pokecenter before the gym.
9. Kanto map 2 (seed ~10032): my Mankey Lv17 FULL HP holding Red Card led into the Officer's Fire trainer (+2) and came out FAINTED (0/44). Neutral typing + Red Card did NOT save it. Confirms note 6 hard: every battle node can cost the lead its whole bar regardless of items/matchup. Rule: before any trainer node, name which body I am willing to lose, and never lead my gym-critical counter into filler trainers. Budget: heal at the last pokecenter before the gym, and prefer catch/item nodes over trainers when team HP is thin.
10. Kanto map 1 (seed ~10040): I took the layer-3 Fire Officer trainer with a full-HP on-level Water counter lead (Horsea Lv11) and it STILL came out 0 HP — and by layer 5 four of six mons were fainted with the pokecenter only at layer 7. Confirms note 6 again: budget ONE expendable body per trainer fight max, and never take back-to-back trainers before a heal. Map 1 specifics seen: catches at layers 1-2, move tutor at n5_0, trade at n4_0, pokecenter at n7_1, gym at layer 8. Route catch-catch-catch -> tutor -> skip trainers -> heal n7_1 -> gym looks safest.
11. ALWAYS call set_lead before entering a battle node — it is free and does not cost the turn. Seed ~10050 map 0: I planned "Seel leads into the Firebreather" but never actually called set_lead, so Lv7 Bulbasaur led instead and fainted from full HP. The plan in my head does nothing; only the slot-0 mon fights. Rule: before every play() on a battle node, check who is marked "<- leads" on the team line and set_lead the intended counter if it isn't already there.

### How it grew

| run | seed | notes kept | badges |
|--:|--:|--:|--:|
| 1 | 10000 | 1 | 1 |
| 11 | 10010 | 5 | 1 |
| 21 | 10020 | 8 | 0 |
| 31 | 10030 | 8 | 1 |
| 41 | 10040 | 11 | 0 |
| 50 | 10049 | 11 | 1 |

