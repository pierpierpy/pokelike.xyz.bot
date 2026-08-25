# deepseek/deepseek-v4-flash under harness `v7`

This page holds the notes the model kept while it played. A note is whatever the model chose to write down through its `remember` and `revise` tools, so the notebook records what the model thought worth keeping. Some of it was learned in play and some of it the model already knew, and the notebook does not distinguish them.

The route the model planned for each run is on its own page under `plans/`.

## Pass `20260823-005156-9f6e`, `--set reasoning=low`

The pass played 50 runs and averaged 1.46 badges.

### The notebook at the end

1. A map choice closes ALL alternatives on that layer. Check what_lies_ahead before picking, not after.
2. Kanto map0: Officer (Fire) trainer took out my Bulbasaur. Fire beats Grass. Don't lead Grass into Fire trainers even for XP.
3. Kanto map1 trainers at L12-16. Hiker (Rock/Ground) still hits hard vs Water if underleveled. Be L13+ with 70%+ HP before fighting map1 trainers. My L11 Squirtle got OHKOed.
4. Kanto map0 gym (Brock): Rock types. Water Bubble beats them clean. Wartortle Lv16 and Tentacool Lv15 handled it easily.
5. Kanto map3 gym (Erika): Grass/Poison types. Psychic hits 4x SE. Bring Kadabra/Alakazam or any good Psychic type. Grass moves are 0.25x vs Grass/Poison (Ivysaur tanks them).
6. Kanto map2 gym (Lt. Surge): Electric types. Ground is IMMUNE to Electric (no damage taken). Dugtrio+Precipice Blades or any Ground type walks it.
7. Kanto map5 gym = Sabrina (Psychic). Fighting types are perfect: resist Psychic at 0.5x and hit Psychic 2x SE. Hitmonlee/Cross Chop beats her. Dark/Ghost also excellent. Psychic vs Psychic is resisted (0.5x).
8. Kanto map0: n6_1 (catch) leads to pokecenter+trainer on L7, n6_0 (item) cuts off pokecenter. Never skip the heal path before Brock.
9. Kanto map1 gym (Misty): Water types. Grass/Electric lead walks it. Oddish Lv12+ with Magical Leaf (Grass) hits Water 2x SE. Don't bring Water leads - they're resisted.
10. BOY gives Kanto starters (Bulbasaur/Charmander/Squirtle). GIRL likely gives different starters. Squirtle is best for Brock (Water beats Rock).
11. BOY starter screen offers Bulbasaur(0), Charmander(1), Squirtle(2). Squirtle best for Brock (Water beats Rock).
12. Kanto map1: Fisherman trainers use Water types. Exeggcute (Grass/Magical Leaf) leads and hits 2x SE. Very safe XP.
13. Map0 Kanto: the map has item(0) and catch(1) branches on L6. The catch branch (n6_1) leads to pokecenter on L7 BEFORE the gym. The item branch skips it. Always take the catch side for the heal.
14. Kanto map0 L6: n6_0 (catch) and n6_1 (move tutor) both lead to pokecenter on L7 before Brock. n6_2 (item) skips the heal. Always take a path that leads to the pokecenter before the gym - the heal is essential.
15. Kanto map3: Bug Catcher trainers on L4 may carry Bug/Poison (Beedrill). Mr. Mime (Fairy) takes 2x SE Poison. Lead a pure Psychic (Kadabra) not Psychic/Fairy vs Bug Catchers. Bug is 0.5x to Fighting and 0.5x to Rock - Hitmonchan or Rock type is safer.
16. Kanto map4 (Koga - Poison gym): Graveler (Ground) is IMMUNE to Poison - best lead. Rock Slide is neutral. Mr. Mime (Psychic/Fairy) hits 2x SE but Fairy takes 2x SE from Poison - risky. Jynx (Psychic/Ice) is neutral to Poison, hits 2x SE with Psychic.
17. Kanto map0: BOY gives Kanto starters (Bulbasaur/Charmander/Squirtle). GIRL likely gives different region starters. Squirtle is proven best for Brock (Water beats Rock).
18. Kanto map3 L4: Bug Catcher had Bug/Poison types that swept my team (Mr. Mime took 2x SE Poison). The Bug Catcher trainer is deceptively dangerous - don't lead Fairy types vs Bug trainers, they may have Poison subtypes.
19. Kanto map0: BOY gives Kanto starters (Bulbasaur/Charmander/Squirtle). Squirtle is proven best for Brock. GIRL gives non-Kanto starters (Johto/Hoenn/Sinnoh).
20. Kanto map1 L3: n3_2 (catch) can give Tangela L10 (Grass/Magical Leaf). Perfect Misty counter. Worth taking over trainer paths early.
21. Squirtle start (Water) is proven best for Kanto map0 Brock (Rock). Water Bubble beats Rock 2x SE. Don't pick Charmander into Rock gym.

### How it grew

| run | seed | notes kept | badges |
|--:|--:|--:|--:|
| 1 | 10000 | 3 | 1 |
| 11 | 10010 | 9 | 1 |
| 21 | 10020 | 13 | 1 |
| 31 | 10030 | 16 | 1 |
| 41 | 10040 | 17 | 1 |
| 50 | 10049 | 21 | 1 |

## Pass `20260823-005204-df0f`, `--set reasoning=high`

The pass played 50 runs and averaged 1.66 badges.

### The notebook at the end

1. First run of a region: everything is unknown. Catch early, heal before gyms, and write down EVERY gym leader's types and levels.
2. Kanto Gym 1 (Brock): Rock/Ground types. Psyduck's Water Bubble 4x effective. Lead Water type and it's an easy sweep.
3. Kanto Gym 2 (Misty): Water types. Ivysaur with Energy Ball (90 Grass STAB, 4x on Water) one-shots her whole team at Lv22. Easiest sweep if you have strong Grass.
4. Kanto Map 2 Scientist (Electric/Poison) at Lv5 is dangerous - it fainted my Lv15 Kadabra and Lv22 Psyduck. Trainers with type advantage can one-shot. Always check if your lead has enough bulk to survive a hit before a trainer fight, not just if you can KO back.
5. Map 3 Kanto Firebreather (Fire types): even with Psyduck's Water Bubble 4x, took damage that fainted Psyduck. Firebreathers hit hard. Heal Psyduck or swap to tankier lead next time.
6. Kanto Map 3 has TWO Firebreather trainers (layers 2 and 3). They fainted 4/6 of my team even with type advantage. If you see a second Firebreather, consider healing between or avoiding one. They hit HARD.
7. Start of run: pick character (no gameplay impact), then choose starter. Always check map layers before choosing - use what_lies_ahead.
8. Kanto starter: Squirtle (Water 4x vs Rock/Ground, resists Rock) safest for Brock. Bulbasaur's Grass is ALSO 4x vs Rock/Ground but takes 2x from Rock moves. Charmander's Fire is 0.5x - worst pick. Squirtle is the safe pick for Kanto map 0.
9. Kanto Map 0: safe path is catch→item→wild→move tutor→item(pokecenter layer 7). Bulbasaur with Expert Belt+Solar Beam one-shots Brock. Heal before gym always.
10. Kanto Map 0: n3_0 (item) leads to trainer on n4_0 (n4_1 also trainer). The two catch nodes (n5_0, n5_1) are reachable from both. Plan: item→trainers for levels→catches→pokecenter→gym.
11. Kanto starter analysis: Squirtle (Water 4x vs Rock/Ground) safest for Brock. Bulbasaur's Grass is ALSO 4x vs Rock/Ground (not 0.25x), but Bulbasaur is Poison type which is weak to Ground moves. Charmander's Fire is 0.5x - worst pick. Squirtle is the safe choice.
12. Kanto Map 1: item (n2_1) leads to catch+trainer on layer 3; n4_1 (catch) leads to trade+trainer on layer 5, then trainer+pokecenter on layer 7 before Misty. Route pattern: item→trainer→catch→trainer→?→trainer→pokecenter→gym.
13. Kanto Map 0 Bug Catcher trainer: even at Lv8, Squirtle fainted to it. Bug moves (like Fury Cutter) are neutral to Water but still deal decent damage. Arrive at Lv10+ for safety, or heal between fights.
14. Kanto Map 1: Tangela (Grass) caught layer 1 is Misty counter. Magical Leaf 40 Grass STAB + Expert Belt (+100% SE) = 480 effective vs Water. Level to Lv15+ for safe sweep. Shell Bell or Expert Belt both work well on Tangela.
15. Kanto Map 0 layer 5 wild battle nearly wiped my Lv6-8 team (Squirtle, Exeggcute fainted). Wild battles hit harder than expected at low levels. Heal at pokecenter before gym is mandatory.
16. Kanto Map 1 Misty (Water gym): all-Water team is useless (Water resists Water). Need Grass (4x) or Electric (2x) type. Catch early on this map for a counter.
17. Kanto Map 1 Scientist (Electric/Poison) hits HARD - wiped 5/6 of my Lv10-14 team even with Rhyhorn's Ground Bulldoze 2x. The Scientist has TWO Pokemon and both hit hard. Arrive with Lv14+ Ground type OR heal between. This trainer is a run-ender if you're underlevelled.
18. Kanto Map 1: pokecenter is at layer 7 (n7_1) before Misty gym at layer 8. Always heal Bellsprout there - Grass 4x vs Water is the Misty counter.
19. Kanto Map 1 layer 7: the ? node is an ITEM, not a catch. If you need a type counter for Misty, don't gamble on ? - take the pokecenter and hope you caught Grass/Electric earlier.
20. Map 5 Fisherman (Water types) fainted 4/6 of my Lv37-47 team. Water trainers hit HARD even with Grass leads. Heal BEFORE Fisherman, not after - or skip it if team is fragile.
21. Parasect's Megahorn is BUG type, not Grass. Bug is neutral vs Water (0.5x). Don't lead Parasect vs Water thinking Megahorn is SE - check the move's type, not the Pokemon's type.
22. Kanto Map 1 layer 3 ? node is a BATTLE, not an item. It fainted my Lv13 Wartortle and Lv12 Bellsprout. Avoid it if your Misty counters are fragile - take the trade instead.
23. Fire is 2x SUPER EFFECTIVE vs Grass, not resisted. I lost Exeggcute leading it vs Officer (Fire). Grass resists Electric (0.5x) and Water (0.5x), but takes 2x from Fire, Ice, Poison, Flying, Bug. Memorize the type chart, don't guess.
24. Kanto Map 2 gym is Lt. Surge (Electric). Need Ground type (immune to Electric, 2x SE). Graveler/Geodude line is perfect - Rock/Ground resists Normal and Flying too. Catch Ground type early on this map.
25. Kanto Map 3 gym is Erika (Grass). Fire type (Charmeleon/Charizard) with Flamethrower 2x vs Grass is the perfect counter. Graveler/Rock types take 4x from Grass - keep in back. Catch Fire type early on this map.
26. Metronome item: dual-type holder uses its OTHER type for attacks. Ivysaur (Grass/Poison) with Metronome uses Poison type - 2x SE vs Grass. Check dual-type Pokemon for hidden type advantages with this item.
27. Kanto Map 5 (after Koga): next gym is Sabrina (Psychic). Need Dark/Ghost/Bug type. Magnezone (Steel 0.5x) best defensive option. Catch early on this map for a Psychic counter.
28. Kanto Map 5 Hiker (Rock/Ground, Lv40+) fainted my Magnezone AND Flareon despite Steel immunity to Ground. These trainers hit EXTREMELY hard - expect casualties even with type advantage. Heal fragile Pokemon before Hiker.
29. Kanto Map 0: catch on layer 1 (n1_0) gives a second body early. With only Squirtle, one bad crit ends the run. Always catch early on map 0.

### How it grew

| run | seed | notes kept | badges |
|--:|--:|--:|--:|
| 1 | 10000 | 6 | 3 |
| 11 | 10010 | 13 | 1 |
| 21 | 10020 | 17 | 1 |
| 31 | 10030 | 21 | 1 |
| 41 | 10040 | 28 | 6 |
| 50 | 10049 | 29 | 3 |

