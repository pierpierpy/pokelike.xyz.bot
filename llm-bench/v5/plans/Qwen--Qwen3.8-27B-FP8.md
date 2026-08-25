# Qwen/Qwen3.8-27B-FP8 under harness `v5`, the routes it planned

A plan is the route the model laid out for the map it was standing on, through its `plan` tool. One entry per run, in the order the runs were played.

The notes the model kept are on its own page under `notebooks/`.

## Pass `20260821-184228-d2d8`

The pass played 50 runs and averaged 0.96 badges.

Its best run was seed 10015 at 8 badges.

**Run 1, seed 10000, 1 badge**

> Map 1 final: heal at pokecenter n7_0 (Onix 17/33, Charmeleon 17/48 hurt) then gym n8_0. Onix (Eviolite tank, Rock STAB) leads unless gym type says otherwise — check gym tooltip and set_lead a super-effective, healthy lead. Abra's 0-power move stays (backup body).

**Run 2, seed 10001, 1 badge**

> Map 1, badge 2 (gym likely Water/Misty). Team: Spearow Lv19 (31/44), Wartortle Lv20 (12/53), Lickitung Lv15 (52/52), Oddish Lv12 (32/32), Oddish Lv13 (34/34), Farfetchd Lv14 (38/38). I'm at item node n7_0; pokecenter n7_1 is now closed (no heal). Keeping the unidentified item in bag for now. Next: gym n8_0. Lead Oddish (Grass, 2x into Water) for the gym. Goal: survive the gym, earn badge 2.

**Run 3, seed 10002, 1 badge**

> Map 1: Team = Squirtle (lead, Surf 80 + Expert Belt, Lv9), Slowpoke (Aqua Jet 50, Lv8), Rhyhorn (Bulldoze 55, Lv6), Oddish Lv8 (Magical Leaf 40), Oddish Lv9 (Magical Leaf 40). L3: taking Bug Catcher (n3_1) for +2 levels — Bug is neutral vs my Water lead, known type, more XP than the wild battle's +1. Both L3 options lead to a forced trainer at L4 anyway. L4: T T T (forced) — CHECK type tooltips, set the right lead. L5: T T ? ? — dodge trainers, take unknowns. L6: o o x — catch for a 6th body. L7: ? + — pokecenter (+) to heal before gym. L8: gym — lead the right Pokemon for its type.

**Run 4, seed 10003, 1 badge**

> Map 1, layer 6, 1 badge. Team HP: Onix 10/32, Nidoran-m 0/33 (fainted), Sandshrew 22/38, Drowzee 38/38, Squirtle 12/38, Growlithe 39/39. Take CATCH n6_1 (free body, keeps pokecenter open) over trainer n6_2 (funnels to another fight, no heal). Release fainted Nidoran-m to make room. -> layer 7: pokecenter n7_0 to heal before gym -> layer 8 gym B, lead the type that beats it. Survival first: heal before the boss.

**Run 5, seed 10004, 1 badge**

> Map 1, gym n8_0, pokecenter n7_0. Capturing Onix Lv14 (Rock/Ground, Rock Throw 50, 33/33, DEF 49) as 3rd body: tanky, Rock move 2x vs Fire/Ice/Flying/Bug, resists Rock/Electric/Poison/Normal/Fire. Team: Goldeen Lv10 Water, Machop Lv12 Fighting, Onix Lv14 Rock/Ground. 3 fainted (Sandshrew/Wartortle/Krabby). Route: pokecenter n7_0 (heal) -> gym n8_0. Lead by gym type: Onix vs Fire/Ice/Flying/Bug, Goldeen vs Rock/Ground/Fire, Machop vs Rock/Normal/Ice/Steel/Dark.

**Run 6, seed 10005, 1 badge**

> Map 1, layer 7. LOST Squirtle + Voltorb (both fainted in layer-6 wild fight — I led low-HP leads). 4 healthy: Lickitung Lv14 37/49 [Eviolite], Rhyhorn Lv14 46/46, Omanyte Lv14 33/33, Exeggcute Lv12 36/36. Take pokecenter n7_1 (index 1) to HEAL all 4 to full before gym B (layer 8). Skip Rocket Grunt (Poison, +2) — Exeggcute 2x weak to Poison, can't afford another loss (note 10). After heal, set lead for gym: pick best-matched healthy Pokémon.

**Run 7, seed 10006, 1 badge**

> Map 1 (1 badge). Team: Squirtle Lv14 (lead, 28/36), Paras Lv13 (26/32), Pinsir Lv12 (37/37), Krabby Lv10 (0/26 fainted). Bag: 2x Rare Candy + Moon Stone (useless on my team). Catching Growlithe Lv14 (Fire, Incinerate 60) — covers my Bug/Grass/Ice weaknesses, diversifies, strongest move. Route: n6_0 (catch Growlithe) → n7_0 (pokecenter, heal) → B (gym). Use a Rare Candy on my gym lead before the boss. Lead the healthiest, well-matched Pokémon.

**Run 8, seed 10007, 1 badge**

> Map 1 (badge 2), gym at layer 8. Team: Squirtle Lv15 Water (lead, Eviolite, 38/38), Spearow Lv14 Flying (19/35), Lickitung Lv11 Normal (40/40), Drowzee Lv10 Psychic (32/32); Cubone Lv10 fainted (4 bodies). Route: n6_2 item (guaranteed item, hope Wide Lens) -> n7_1 pokecenter (full heal before gym) -> n8 gym. Skip the random question node n6_1 to avoid risking a body before the boss. Set the gym lead once I see its type (Squirtle default; Spearow if Electric/Grass; Drowzee if Electric/Fighting/Poison).

**Run 9, seed 10008, 1 badge**

> 2 bodies: Machop (Fighting, 34/34, Choice Band) + Staryu (Water, 30/30). Route: n6_1 (wild battle, +1 level) -> n7_0 (pokecenter, heal if damaged) -> n8_0 (gym). Lead Staryu into n6_1 (never 0x, good resistances). Preserve both bodies for the gym. Use Rare Candy if I get a chance.

**Run 10, seed 10009, 0 badges**

> Layer 6: take n6_0 catch for a 3rd body (Goldeen fainted; down to Pidgey 20/20 + Charmander 12/22) — leads to pokecenter. Skip n6_1 trainer (Fire Pokemon: Charmander's Fire is resisted, Pidgey neutral — too risky at 2 bodies). Layer 7: pokecenter to heal. Layer 8: gym. Lead the highest-level, healthiest, well-matched Pokemon.

**Run 11, seed 10010, 3 badges**

> Map 3, layer 5 (3 badges). At n4_0 (col 0). Team (full 6): Charmeleon Lv30 (53/74, Flamethrower 117 w/Specs), Seel Lv29 (76/76, Bubble 50), Weepinbell Lv24 (65/65, Razor Leaf 65), Ivysaur Lv26 (67/67, Energy Ball 90), Graveler Lv23 (58/58, Rock Slide 75), Machoke Lv24 (72/72, Cross Chop 100). MUST stay col 0 to reach pokecenter n7_0 (only heal before gym; can't move left). Path: n5_0 (wild +1) -> n6_0 (trade +3) -> n7_0 (heal) -> B (gym). n5_1 (col 1) closes the heal path — avoid. Lead Charmeleon (strongest) for the wild battle; heal at n7_0 before the gym.

**Run 12, seed 10011, 1 badge**

> Map 1, 8 layers, gym B at n8_0 (col0). Movement is stay-or-right only, so to reach the gym I MUST stay in col0 every layer: n1_0 catch -> n2_0 battle -> n3_0 trade -> n4_0 catch -> n5_0 trade -> n6_0 move tutor -> n7_0 battle -> n8_0 gym. The pokecenter n7_1 (col1) is a DEAD END (can't reach the col0 gym from it), so I skip it and manage HP instead. Catch at n1_0 and n4_0 for 4th/5th bodies; trade at n3_0 and n5_0 for stronger mons; tutor at n6_0 to upgrade a key move. No heal before the gym, so keep leads healthy and set the best-matched lead before n7_0 and the gym.

**Run 13, seed 10012, 1 badge**

> Map 1, gym B at n8_0. Squirtle fainted at n5_1 (lost my best lead, Surf 80). Remaining team: Magnemite Lv10 19/25, Pidgey Lv10 28/28, Ekans Lv9 25/25, Onix Lv10 27/27, Drowzee Lv11 34/34. Path: n6_1 (battle, +1 lvl) -> n7_1 (POKECENTER, heal) -> n8_0 (gym). Lead Drowzee (Lv11, 34/34, healthiest) into n6_1. After the pokecenter, lead the healthiest well-matched Pokemon into the gym.

**Run 14, seed 10013, 1 badge**

> Map 1, gym B at L8 col0, heal + at L7 col1. Team: Rhyhorn Lv16 (lead, Leftovers, Ground/Rock), Wartortle Lv17 (Red Card, Water), Lickitung Lv14 (Normal), Ponyta Lv12 (Fire). Route: n5_1 (Scientist, Electric/Poison — Rhyhorn immune to Electric, 2x vs Poison) -> L6 col1 (x, wild +1) -> L7 col1 (+, heal) -> L8 col0 (gym). Lead Rhyhorn for Electric/Poison; verify each connection with what_lies_ahead before closing a door.

**Run 15, seed 10014, 1 badge**

> Map 1 route to gym: n4_1 (item) -> n5_1 (trainer, +2 lv) -> n6_1 (trainer, +2 lv) -> n7_0 (pokecenter, heal) -> n8_0 (gym). Goal: reach gym at ~Lv18-20 with full HP. Lead depends on gym type (Rhyhorn Ground vs Rock/Fire/Elec/Poison/Steel; Charmeleon Fire vs Grass/Ice/Bug/Steel; Drowzee Psychic vs Fighting/Poison). Reassess connections with what_lies_ahead at each layer to ensure I can reach the pokecenter n7_0 before the gym.

**Run 16, seed 10015, 8 badges (best)**

> Map 8 (final, 8 badges). Team: Lapras Lv60 (0/226 FAINTED), Charizard Lv91 (95/242, Flamethrower 90 Fire, Quick Claw), Parasect Lv81 (188/188, Bug Bite 50 Bug), Omastar Lv79 (199/199, Ancient Power 50 Rock), Machamp Lv74 (217/217, Cross Chop 100 Fighting), Starmie Lv82 (0/190 FAINTED, Psycho Boost 100 Psychic, Metronome). Bag: Scope Lens, Rare Candy, Mystic Water, Lucky Egg, Red Card. ROUTE: layer7 + (pokecenter, heal before gym) -> layer8 B (gym, pick lead by revealed type). Priority: heal team, don't lose more Pokemon, right gym lead. After pokecenter, set lead based on gym type.

**Run 17, seed 10016, 1 badge**

> Map 1, 4 bodies: Squirtle Lv14 (Water, Hydro Pump 110, FAINTED 0/36 - MUST revive at pokecenter), Tentacool Lv14 (Water/Poison, Bubble 50, 32/35), Exeggcute Lv13 (Grass/Psychic, Magical Leaf 40, 38/38), Cubone Lv13 (Ground, Bulldoze 55, 8/36, LEAD). DECISION: take n6_1 item (free value, no body risk) over n6_0 Hiker (+2 levels but risks losing another body; I already lost Squirtle to a Hiker). Then n7_0 pokecenter (REVIVE Squirtle + full heal) -> n8_0 gym (set Squirtle as lead, Water SE vs Rock/Ground). 4 bodies into the gym.

**Run 18, seed 10017, 1 badge**

> Map 1, layer 6 (item). Equipped Leftovers on Mankey (lead, +10% HP/round). Team: Mankey Lv14 (lead, Leftovers), Sandshrew Lv14, Squirtle Lv13 (fainted), Ponyta Lv12. Next: pokecenter layer 7 to fully heal. Then gym B layer 8 — pick lead by the gym's revealed types; Leftovers on the lead helps it survive the multi-round fight.

**Run 19, seed 10018, 5 badges**

> Map 5, 5 badges, 1 layer to gym (pokecenter n7_1 then gym n8_0). Team: Blastoise 105/139 Lv50 (lead, Leftovers, Hydro Pump 110), Arcanine 93/122, Dodrio 102/102, Dugtrio 15/81, Slowbro 126/126, Aerodactyl 114/114. Bag: Rare Candy, 2x Sacred Ash, Expert Belt. Route: KEEP Expert Belt in bag (equip on the right lead only after seeing the gym's type at n8_0) -> n7_1 pokecenter (heal all) -> n8_0 gym. Pick lead by gym type (Blastoise default); Sacred Ashes in reserve.

**Run 20, seed 10019, 1 badge**

> Map 1, layer 6. ONLY Kabuto alive (20/32, Rock/Water, Rock Throw 50). Bug Catcher took 5/6. Plan: (1) n6_0 move_tutor (SAFE, no fight) to buff Kabuto's Rock Throw to a Tier-2 Rock move. (2) Layer 7 pokecenter to heal Kabuto to full 32/32. (3) Layer 8 gym with Kabuto at full HP. Kabuto resists Water/Rock/Steel/Fire/Normal but is 4x weak to Electric — pray the gym isn't Electric. Do NOT fight the Fisherman (Water 2x vs Kabuto's Rock).

**Run 21, seed 10020, 1 badge**

> Map 1, 6 bodies (5 living: Mankey Lv10, Ekans Lv10, Squirtle Lv11+Eviolite, Vulpix Lv10, Cubone Lv14 Ground; Rhyhorn fainted). Squirtle = gym lead (Surf 80, broadest 2x). Route: catch Cubone (n6_1) -> n7_0 pokecenter (heal Squirtle) -> n8_0 gym. Use Rare Candy on Squirtle before boss. AVOID trainers (note 8).

**Run 22, seed 10021, 1 badge**

> Map 1, 5 bodies (Squirtle Lv11 lead w/ Red Card, Exeggcute Lv10, Rhyhorn Lv6, 2x Seel Lv6). Priority: LEVEL UP (3 bodies at Lv6) + heal before gym. Route: n1_1 battle (+1 lvl, keeps trainer open) -> layer 2 trainer (T) for XP -> layer 3 item (i) for a useful item -> layer 4/5 battle/trainer for levels -> layer 6 battle -> layer 7 pokecenter (+) to heal -> layer 8 gym (B). Arrive at gym with leveled, healed team and strong Water lead.

**Run 23, seed 10022, 1 badge**

> Map 1, 5 healthy bodies (Squirtle W Lv12 14/32, Voltorb E Lv11, Cubone G Lv10, Kabuto R/W Lv11, Growlithe F Lv12; Bellsprout fainted). At L5: n5_1 move_tutor — buff Growlithe Incinerate60->Flamethrower90 (Lv12, 35/35 full HP, 2x vs Grass/Ice/Bug/Steel = best gym lead). L6: n6_1 trainer (reaches pokecenter) — lead a resister. L7: n7_1 pokecenter (heal Squirtle). L8: B gym — lead Growlithe (Flamethrower) if type matches, else best resister.

**Run 24, seed 10023, 0 badges**

> Map 0, layer 6, 3 bodies all full HP. Forced to fight (no safe node at layer 6). Take n6_1 Fisherman (Water, known type): my lead Charmander (Fire, Flamethrower 90 STAB, Quick Claw) is 2x SE vs Water and likely KOs first; +2 levels. Then n7_0 pokecenter to heal before the gym — n6_1 leads to the pokecenter, whereas n6_2 (wild) would force a 2nd fight (n7_1) with no heal. Then gym B at layer 8 with a full-HP, well-matched lead.

**Run 25, seed 10024, 0 badges**

> Map 0, 5 bodies: Squirtle Lv5 (Water, lead), Weedle Lv4 (Bug/Poison), Paras Lv4 (Bug/Grass), Staryu Lv2 (Water), Geodude Lv4 (Rock/Ground, Electric-immune). Rare Candy pending in bag. Route: n6_1 -> n7_0 pokecenter (+, use Rare Candy on lead here) -> n8_0 gym B. Avoid all fights (low level). Lead Squirtle (Water) for any unavoidable fight.

**Run 26, seed 10025, 1 badge**

> Map 1, 4 healthy bodies (Squirtle Lv11 30/30 [Assault Vest], Drowzee Lv10 32/32, Gastly Lv11 27/27, Magnemite Lv10 9/25). Route: n5_0 move tutor (buff gym lead's move, no fight) -> n6_0 trade (evaluate offer, likely keep team) -> n7_0 pokecenter (heal) -> n8_0 gym B. Use Rare Candy on gym lead. Pick lead by type matchup once gym types revealed. Skip all fights (n6_1 trainer, n7_1 unknown).

**Run 27, seed 10026, 1 badge**

> Map 1, layer 6: take the item (n6_0) — free, avoids the Electric/Poison Scientist (2x vs my Water-heavy team), leads to pokecenter (n7_0) to heal before the gym (n8_0). Onix fainted in the Bug Catcher fight; I have 5 healthy bodies. Set the gym lead after the pokecenter based on the gym's types; Charmander (Lv15, Choice Specs, Fire) is my top candidate.

**Run 28, seed 10027, 1 badge**

> Map 1 (badge 1), 4 bodies: Psyduck Lv15 (Water, lead, Choice Scarf), Charmeleon Lv16 (Fire), Diglett Lv8 (Ground), Drowzee Lv9 (Psychic). Layer 5: TAKE trainer n5_1 (Fire) — my Water lead is 2x SE vs Fire AND resists it, +2 levels, and it's the ONLY path to the M move-tutor at layer 6. Layer 6: M tutor (buff gym lead's move Tier1->Tier2). Layer 7: + pokecenter (heal before gym). Layer 8: B gym. Keep 4+ bodies.

**Run 29, seed 10028, 1 badge**

> Map 1, 4 bodies (Ponyta Lv12 Fire 13/34, Rhyhorn Lv10 Ground/Rock 28/36, Seel Lv10 Water 33/33, Tangela Lv11 Grass 35/35). Lost Squirtle to Bug Catcher. L5: n5_1 (random) — avoid guaranteed Ace Trainer fight (4 bodies, one damaged). L6: M (move tutor) — safe, buff gym lead. L7: + (pokecenter) — heal before gym. L8: B (gym) — lead by gym type: Rhyhorn Earthquake (broad 2x Rock/Elec/Poison/Fire/Ice), Tangela Grass (2x Water/Ground/Rock/Fire), Ponyta Fire (2x Grass/Ice/Bug/Steel), Seel Water (2x Rock/Ground/Fire).

**Run 30, seed 10029, 1 badge**

> Map 1, 6 healthy bodies (Squirtle Lv9, Spearow Lv8, Diglett Lv8, Ponyta Lv9, Tauros Lv10, Machop Lv13), passives Expert Belt + Leftovers. n7_0 Scientist (Electric/Poison): lead Diglett (Ground = immune to Electric, resists Poison, Earthquake 2x both) for +2 levels. Then n8_0 gym B. Gym lead: Machop (Cross Chop, no 4x weakness) unless the gym's revealed type favors another.

**Run 31, seed 10030, 0 badges**

> Map 0, 3 bodies (Charmander Lv7 lead 17/22, Goldeen Lv6 21/21, Paras Lv4 16/16). Trade was a no-op. n5_0 MOVE TUTOR (safe, buff my lead). Layer 6: battle (x) — pick a healthy well-matched lead. Layer 7: + (pokecenter) to heal before gym, or T (trainer) +2 levels if healthy. Layer 8: GYM with a healthy well-matched lead. Target ~Lv9-11 at the gym.

**Run 32, seed 10031, 0 badges**

> Map 0, 3 healthy bodies (Charmander Lv9 lead, Geodude Lv8, Poliwag Lv4); Oddish fainted. Layer 7: take Leftovers (run-wide passive, 10% HP/round in every battle). Layer 8: set a healthy, well-matched lead before the gym B — Charmander leads unless the gym's type is Water/Rock/Ground, in which case swap to Geodude or Poliwag.

**Run 33, seed 10032, 0 badges**

> Map 0, 2 bodies (Charmander Lv9 lead w/ Flamethrower 90 + Charcoal, Lickitung Lv8 full backup). Layer 7: take trainer n7_0 (Scientist Electric/Poison, 1 Pokemon on map 0) for +2 levels — controlled neutral fight per note 7 (Charmander Fire is neutral to both Electric and Poison), healthy Lickitung backup ready. Then gym B at layer 8. If Charmander is badly damaged after the trainer, reassess the lead for the gym based on its revealed type.

**Run 34, seed 10033, 0 badges**

> Map 0, 2 bodies (Charmander Lv6 7/20 HP lead, Mankey Lv5 19/19), Leftovers in bag. Layer 5: take safe ? node n5_0 (no fight, chance at 3rd body/heal) over risky wild battle. Then layer 6 trainer (level up), layer 7 HEAL at pokecenter n7_0, gym n8_0. Keep Mankey healthy as backup lead.

**Run 35, seed 10034, 1 badge**

> Map 1, 4 bodies (Poliwag fainted vs Hiker — confirms note 6: Rock/Ground KOs even a 2x-SE Water lead). Sandshrew Lv18 (26/46, Ground EQ 100 ph), Charmeleon Lv19 (10/51, Fire FT 90 sp), Oddish Lv14 (36/36, Grass), Omanyte Lv15 (35/35, Rock/Water). Expert Belt passive in bag. Layer 7: take pokecenter n7_0 (team damaged so NOT a no-op; no 2x-SE+resist lead vs Water Fisherman, note 8 skip <=4 bodies). Layer 8 gym: set lead by gym types — Sandshrew (Ground 2x 5 types) or Charmeleon (Fire) as strongest, both full after heal.

**Run 36, seed 10035, 0 badges**

> Map 0, 3 bodies (Charmander Lv8 Fire 19/24, Mankey Lv7 Fighting, Voltorb Lv7 Electric). Buff Charmander → Flamethrower (strongest, most versatile gym lead; Fire neutral vs most types). Layer 7: pokecenter (+) to heal before gym (Charmander not full, only 3 bodies) OR trainer (T) for +2 levels — decide by HP. Layer 8: gym (B) with buffed Charmander leading, Mankey/Voltorb as type-coverage backups.

**Run 37, seed 10036, 1 badge**

> Map 1, 5 healthy bodies (Rhyhorn 0/46 down, Sacred Ash in bag unused, Psyduck 15/38, rest full). Route: n7_0 (pokecenter, heal Psyduck 15→38) → n8_0 (gym, lead Charmander Lv15 Flamethrower 90). Pokecenter is a real heal (Psyduck low), not a no-op, so it beats the random-event question node right before the boss. Set Charmander as lead at the gym.

**Run 38, seed 10037, 1 badge**

> Map 1, Sandshrew fainted vs Fisherman. 3 bodies: Poliwag Lv14 11/35, Charmander Lv15 8/36, Tangela Lv12 37/37 (only healthy). Leftovers in bag. Take move_tutor (n6_1, SAFE buff) — do NOT fight Hiker (n6_0, 3-Pokemon Rock/Ground physical, note 6 KOs even a SE lead) with a damaged team. Then pokecenter (n7_0) to heal. Then gym (n8_0) with the best healthy lead.

**Run 39, seed 10038, 1 badge**

> Map 1, 5 full-HP bodies: Charmander Lv11 (lead, Flamethrower 90 Fire sp STAB + Choice Specs), Oddish Lv10, Onix Lv9, Staryu Lv12 (Water), Kabuto Lv13 (Rock/Water). Layer 6: KEEP Expert Belt (run-wide passive, +100% SE, note [5]) — beats niche Metronome and defensive Assault Vest. Still have Rare Candy in bag to use on gym lead. Layer 7: wild n7_0 (+1 level; pokecenter n7_1 is a no-op at full HP, note [12]). Gym B n8_0: set_lead the best-matched healthy body once I see the gym's types — Staryu/Kabuto (Water) answer Rock/Ground/Fire, Charmander (Fire) answers Rock/Grass/Ice/Steel.

**Run 40, seed 10039, 0 badges**

> Map 0, layer 6, 2 bodies (Lickitung Lv11 30/40 leading, Charmander Lv12 8/31). Take n6_1 Officer (Fire, +2 levels, neutral for Lickitung) — keeps battle+pokecenter open at layer 7. Layer 7: pokecenter n7_0 to heal (2 bodies, low HP → heal over +1 level). Layer 8: B gym with healthy Lickitung lead. Priority: heal before gym, never go in with low HP or 1 body.

**Run 41, seed 10040, 1 badge**

> Map 1, layer 5, 5 healthy bodies (Charmeleon Lv16 Fire 16/44, Drowzee Lv15 Psychic 43/43, Seel Lv15 Water 32/44 [Mystic Water], Sandshrew Lv15 Ground 40/40, Machop Lv12 Fighting 38/38). Route: n5_3 trade (safe, +3 to one body — upgrade weakest Machop) -> n6_2 trade (2nd +3 to another body) -> n7_0 pokecenter (heal before boss) -> n8 B gym. Two safe +3 boosts + a heal = strong no-fight route to the gym. Set gym lead once I know its types.

**Run 42, seed 10041, 0 badges**

> Map 0, at layer-5 item node. Team: Charmander Lv7 (11/22, lead), Krabby Lv6 (19/19), Magnemite Lv6 (19/19). Bag: Wide Lens, Rare Candy. Take Rare Candy (use on lead → Lv10). Layer 6: trade $ (+3 lvl to weakest body) or item 'i'. Layer 7: pokecenter + to heal before boss. Beat gym B at layer 8. Keep Krabby + Magnemite healthy as backup leads.

**Run 43, seed 10042, 0 badges**

> Map 0 final stretch, 3 bodies (Charmander Lv6 lead [Wide Lens], Slowpoke Lv5, Magnemite Lv5), all full HP. Take move tutor n6_1 (buffs strongest lead Charmander) — it keeps BOTH layer-7 options open (wild battle +1 level OR pokecenter). At layer 7: pokecenter is a no-op at full HP, so take the wild battle for +1 level if the matchup is safe, else pokecenter. Then gym B (n8_0). Set lead by type before the gym.

**Run 44, seed 10043, 0 badges**

> Map 0 final: n7_1 pokecenter to heal Slowpoke (14/32→full) — safe, no fight, I have only 2 bodies so no risk. Then B gym. Set lead based on gym's types when visible: Charmander Lv9 Flamethrower (90 sp Fire STAB) is my strongest; Slowpoke Lv8 Aqua Jet (50 ph Water STAB, priority) is backup. Pick the lead whose move type beats the gym's lead.

**Run 45, seed 10044, 1 badge**

> Map 1, badge 1, 6 bodies (Charmander Lv15 5/36, Seel Lv14 42/42, Rhyhorn Lv14 16/46, Drowzee Lv14 40/40, Pinsir Lv12 37/37, Oddish Lv13 34/34). L7: pokecenter n7_1 to heal Charmander+Rhyhorn before boss (question n7_0 is a gamble that could KO a body). Set Rhyhorn (Ground/Rock, 2x vs Electric/Fire, bulkiest 46HP) as lead for boss. L8: B gym.

**Run 46, seed 10045, 0 badges**

> Map 0, Charmander Lv6 + Exeggcute Lv5 (2 bodies). Take catch n3_1 for a 3rd body (breadth before more trainers). Then take the Poison trainer (Exeggcute Grass is 2x) for +2 levels. Work down through level nodes, heal at + (n7_0) before gym B (n8_0).

**Run 47, seed 10046, 0 badges**

> Map 0, 3 bodies all healthy: Charmander Lv7 (lead, Fire-sp Incinerate 60 STAB), Voltorb Lv6 (Elec-sp), Meowth Lv6 (Normal-ph). Route: n5_0 move tutor (buff Charmander's move) -> n6_0 trade (+3 levels, pick weakest body) -> n7_0 pokecenter (heal) -> B gym. Keep Charmander leading; Voltorb/Meowth ready as backup.

**Run 48, seed 10047, 1 badge**

> Map 1: layer 6 take n6_0 catch (safe 6th body, no fight) → layer 7 pokecenter + to heal Charmander (7/36) and the team before the gym. Layer 8: gym B. Set a healthy lead (Staryu/Eevee) for the gym once I see its type; keep Charmander as a backup.

**Run 49, seed 10048, 0 badges**

> Map 0: n4_0 (question) → M move tutor (layer 5, buff Charmander gym lead) → $ trade (layer 6, +3 levels on weakest body Krabby) → + pokecenter (layer 7, heal before boss) → B gym (layer 8). Lead Charmander (Fire) into the gym; Krabby (Water) as backup for Rock/Ground.

**Run 50, seed 10049, 1 badge**

> Map 1, 5 bodies (Horsea 13 [3/30 hurt], Mankey 13, Charmander 12, Magnemite 10, Tangela 12), Leftovers in bag. L5: item n5_1 (guaranteed value, keeps all of L6 open). L6: grab another item (n6_1/n6_2) if useful, else question n6_0. L7: pokecenter + to heal before gym (Horsea at 3/30). L8: gym B — set lead by gym type (check tooltip).

