# inclusionai/ling-3.0-flash under harness `v7`, the routes it planned

A plan is the route the model laid out for the map it was standing on, through its `plan` tool. One entry per run, in the order the runs were played.

The notes the model kept are on its own page under `notebooks/`.

## Pass `20260824-153252-176e`, `--set reasoning=medium`

The pass played 50 runs and averaged 1.12 badges.

Its best run was seed 10021 at 4 badges.

**Run 1, seed 10000, 1 badge**

> n5_0 or n5_1 for random event -> trade node at layer 6. Trade Voltorb or Seel for a stronger Pokemon, then work toward gym at layer 8. Prioritize trades that give type coverage against Fire/Water trainers.

**Run 2, seed 10001, 1 badge**

> n1_0 catch to get a second Pokemon (team insurance), then work through trainers on layers 2-6 to level up, use pokecenter at n7_0 before the gym at n8_0, and heal before the boss fight.

**Run 3, seed 10002, 1 badge**

> Take n6_0 (move tutor) to potentially teach a strong move, then go directly to pokecenter at layer 7 to heal before the gym at layer 8. Avoid the catch at n6_1 since we already have 6 Pokemon and the battle there would cost HP before healing.

**Run 4, seed 10003, 1 badge**

> Catch at n3_1 to get a 6th team member (full team = max survivability). Then work through the remaining layers: grab items, heal at pokecenter before the gym, and use move tutor if available. The gym is at layer 8, so I need to be well-leveled and healed by then.

**Run 5, seed 10004, 2 badges**

> n4_1 (battle + trainer) for maximum levels before the gym. Then navigate through layer 5-6 to reach pokecenter at layer 7, then gym at layer 8. We need levels — our team is Lv16-22 and the Elite Four will be tough.

**Run 6, seed 10005, 1 badge**

> Catch at n4_2 to add a 3rd Pokemon (only 2 alive — Seel and Magnemite). Then work down through trainers for levels, reach pokecenter at layer 7 before the gym at layer 8. Heal before the boss.

**Run 7, seed 10006, 0 badges**

> n1_0 catch for a second body (breadth early), n1_1 wild battle for +1 level, then work down through the map toward the gym at layer 8. Heal at pokecenter before the gym boss.

**Run 8, seed 10007, 1 badge**

> n1_0 catch for a second body (Bulbasaur alone is fragile), then n2_0 or n2_1 trainer for levels, heal at pokecenter before the gym boss at layer 8.

**Run 9, seed 10008, 2 badges**

> n2_0 trainer for +2 levels (better than wild battle's +1), then head toward pokecenter at layer 7 before gym boss at layer 8. Need to level up before the boss — trainers give more XP than wild fights. Heal at pokecenter before the gym.

**Run 10, seed 10009, 1 badge**

> n1_0 (catch) first to get a 4th Pokemon for safety, then work through trainer nodes on layers 2-5 for levels, heal at pokecenter layer 7, then gym at layer 8. Catch early is cheap insurance — a 4-Pokemon team survives one more faint than 3.

**Run 11, seed 10010, 2 badges**

> n1_0 catch (get a second Pokemon for insurance), then work through trainers on layers 2-6 to level up, heal at n7_0 pokecenter before the gym, and beat the gym leader at n8_0. Prioritize catching early and healing before the boss.

**Run 12, seed 10011, 1 badge**

> n1_0 catch (get a 4th Pokemon for insurance), then work through trainers on layers 1-2 for levels, heal at pokecenter before the gym boss at the bottom. Prioritize catching early and healing before the gym.

**Run 13, seed 10012, 1 badge**

> n6_1 trade (upgrade Magnemite to Lv11 and gain access to pokecenter on next layer) → heal at pokecenter → gym at layer 8. The trade path is better because it leads to both a battle and a pokecenter, while the trainer path only leads to a battle. We need the heal before the gym.

**Run 14, seed 10013, 3 badges**

> n2_1 battle for +1 level and access to item node on next layer, then work through the map toward pokecenter before the gym boss at layer 8. Prioritize healing at pokecenter before the gym. Map 2 has not been mapped yet — need to note trainer types as I encounter them.

**Run 15, seed 10014, 0 badges**

> n1_0 catch (get a second Pokemon for safety), then work through trainers on layers 2-4 for levels, grab the move tutor M on layer 5, heal at pokecenter + on layer 7, then face the gym leader B on layer 8. The catch early is cheap insurance — a team of one is one faint from the end.

**Run 16, seed 10015, 1 badge**

> Map 1 route: n1_0 catch (add 5th Pokemon for depth), n2_1 trainer for levels, n3_2 trainer for levels, n4_2 open (skip), n5_1 trainer for levels, n6_0 wild for levels, n7_1 pokecenter to heal before gym, n8_0 gym boss. Goal: arrive at gym at full HP with leveled team. Need to identify gym type from tooltip when I reach it.

**Run 17, seed 10016, 1 badge**

> n1_0 catch for a second body (team depth is survival), n2_1 wild battle for early XP, n3_2 T trainer for levels, n4_2 M move tutor for stronger STAB, n7_0 + pokecenter to heal before the gym, n8_0 B gym boss. Prioritize catching and leveling before the gym; heal at pokecenter every time before the boss.

**Run 18, seed 10017, 1 badge**

> n1_1 battle for +1 level (get a quick boost before trainers), then hit trainers on layers 2-3 for XP, grab the item on layer 6 if useful, heal at pokecenter on layer 7, then gym on layer 8. Prioritize level-ups over catches since I already have 3 Pokemon with good type coverage (Grass/Poison, Ground, Water).

**Run 19, seed 10018, 0 badges**

> n1_0 catch (get a second Pokemon for team breadth), then work through trainers on layers 2-4 for levels, hit pokecenter n7_0 before the gym at n8_0. Grass lead (Bulbasaur) beats Fire trainers on map 0.

**Run 20, seed 10019, 1 badge**

> n7_0 (pokecenter) to heal the team before the gym boss — Goldeen is at 13/38 HP and the gym is one node away. After healing, go to n8_0 (gym leader). Healing before the gym is critical — I lost runs by skipping it.

**Run 21, seed 10020, 0 badges**

> Start with Bulbasaur (Grass/Poison) as lead — strong against Fire-type trainers on map 0 (Officer n2_0, Firebreather n2_1). Route: catch a second Pokemon early, level up through trainers, heal at pokecenter before the gym boss. Grass lead handles Fire trainers on map 0.

**Run 22, seed 10021, 4 badges (best)**

> n3_1 (trainer, +2 levels) for guaranteed XP before the gym. Then work down through layers 4-7, prioritizing trainers for levels, catching if a team slot is empty, and always choosing the pokecenter path before the gym boss on layer 7-8.

**Run 23, seed 10022, 1 badge**

> n1_0 catch for a 6th team member (Bulbasaur at 5/21 HP is one faint from wipe, need depth), then n2_1 trainer for +2 levels. After that, head toward pokecenter (layer 7) before the gym boss (layer 8). Map 0 has Fire-type trainers (Officer n2_0, Firebreather n2_1) — Grass lead beats them. Heal at pokecenter before the gym.

**Run 24, seed 10023, 1 badge**

> n2_0 catch for a third body (Onix is alone at Lv8 and one faint ends the run), then n2_1 trainer for levels before the gym boss at layer 8. Heal at pokecenter at layer 7 before the gym.

**Run 25, seed 10024, 1 badge**

> n6_1 (move_tutor) to potentially learn a crucial move for the gym, then pokecenter on layer 7 to heal, then question node for more options, then gym boss at layer 8. The move tutor could teach a move that gives us a type advantage against the gym leader, which is more valuable than +2 levels from the trainer.

**Run 26, seed 10025, 1 badge**

> Take n2_1 (battle -> catch, trainer) for levels and a new catch. Then work down through the map: prioritize catch nodes for team breadth, trainer nodes for levels, the move tutor (M) at layer 5, items at layer 5, pokecenter at layer 7, and finally the gym at layer 8. The pokecenter before the gym is non-negotiable — heal fully before the boss.

**Run 27, seed 10026, 1 badge**

> n2_1 trainer (+2 levels, leads to battle + catch) → then through catch/battle nodes toward pokecenter before the gym at layer 8. Prioritize leveling and team depth before the boss.

**Run 28, seed 10027, 1 badge**

> Kanto map 0: catch Bulbasaur (Grass/Poison) as starter — Grass STAB beats the Fire-type trainers on this map (Officer n2_0, Firebreather n2_1). Route through map prioritizing pokecenter before the gym boss, level up via trainers, and set a healthy Grass lead before each Fire-type encounter.

**Run 29, seed 10028, 1 badge**

> n1_0 catch (get a second Pokemon for insurance), then work down through the map layers toward the gym at layer 8, prioritizing the pokecenter (+) node before the gym boss. Fire-type trainers on this map are weak to Grass, so Bulbasaur leads through them.

**Run 30, seed 10029, 3 badges**

> n1_0 catch for a second body (Bulbasaur alone is one faint from death), then work through the map hitting trainers (T) for levels, grab the pokecenter (+) on layer 7 before the gym (B) on layer 8. Avoid unnecessary wild fights early — level up via trainers instead. Fire-type trainers on this map (Officer n2_0, Firebreather n2_1) are beaten by Grass lead, so Bulbasaur walks them.

**Run 31, seed 10030, 1 badge**

> Start at n2_0 (catch) to get a 6th Pokemon for insurance — a full team of 6 is the best survival buffer before the gym boss. Then work through the map hitting trainers for levels, ensuring I reach the pokecenter (+) on layer 7 before the gym boss (B) on layer 8. Need to figure out map 1's gym type as I go.

**Run 32, seed 10031, 1 badge**

> Go to move tutor n5_2 to teach a strong move (likely to Geodude or Drowzee). Then navigate toward pokecenter (+) on layer 7 before gym (B) on layer 8. Set Geodude as lead (full HP, Rock Slide STAB) before any battle. Map types as I encounter trainers.

**Run 33, seed 10032, 0 badges**

> n1_0 catch to add a second Pokemon to the team (breadth early), then n2_0 or n2_1 trainer for levels, then work toward the pokecenter before the gym boss at layer 8.

**Run 34, seed 10033, 1 badge**

> n1_0 catch to add a second Pokemon (team of 1 is fragile), then n2_0 or n2_1 trainer for levels, then work toward the pokecenter before the gym at layer 8.

**Run 35, seed 10034, 1 badge**

> n3_0 catch for a third body (Geodude is my only healthy Pokemon and one faint ends the run), then n3_1 trainer for levels. After that, head to pokecenter before the gym.

**Run 36, seed 10035, 1 badge**

> n1_0 catch to get a second Pokemon (team of 1 is fragile), then n2_0 trainer for levels, n3_1 trainer, n4_0 item, n5_0 pokecenter before the gym, n6_0 gym leader.

**Run 37, seed 10036, 1 badge**

> n6_1 (question) to access pokecenter path, then n7_1 (pokecenter) to heal before the gym, then B (gym boss) at layer 8. Map 1's gym type is unknown — need to discover it. The question node n6_1 is the right choice because it opens the route to pokecenter, which is essential before the gym boss.

**Run 38, seed 10037, 1 badge**

> n3_1 trainer (+2 levels, Electric/Poison) over n3_2 battle (+1 level) — we need levels before the gym. Both open move_tutor+trainer, so take the +2. Then work toward the pokecenter before the gym boss at layer 8.

**Run 39, seed 10038, 1 badge**

> n2_1 trainer (+2 levels, expands options on layer 3) → work through map toward pokecenter on layer 7 → heal before gym boss on layer 8. Prioritize leveling up: trainers give more XP than wild fights and the gym boss will be tough with only Lv8-10 Pokemon.

**Run 40, seed 10039, 1 badge**

> n6_1 Officer trainer (+2 Levels, Fire Pokemon — Bulbasaur or Kabuto counters) -> pokecenter to heal Bulbasaur (10/34 HP) -> then work through remaining nodes -> gym at n8_0. The pokecenter path from n6_1 is critical: Bulbasaur is nearly fainted and we cannot afford to lose another Pokemon before the gym.

**Run 41, seed 10040, 1 badge**

> n5_1 trainer (Bug Catcher, +2 levels) -> layer 6 explore question + trainer nodes -> layer 7 pokecenter to heal (Seel at 10/53 HP is critical) -> layer 8 gym boss. The trainer gives guaranteed XP and opens question + trainer on layer 6 for more options before healing.

**Run 42, seed 10041, 1 badge**

> n1_0 (catch) to add a second Pokemon for insurance, then n2_1 (trainer) for levels, then continue down the map toward the gym, healing at pokecenter before the boss.

**Run 43, seed 10042, 1 badge**

> Start at n1_0 (catch) to get a second Pokemon for team depth. Then work through the map toward the gym, prioritizing pokecenter (n6_0 or n7_1) before the gym boss at n8_0. Catch at layer 1 is cheap insurance — a team of one is one faint from the end.

**Run 44, seed 10043, 1 badge**

> n1_0 (catch) first to get a second Pokemon for insurance, then work through trainers on layers 2-3 to level up, hit the pokecenter at n7_1 before the gym boss at n8_0. Lead with Bulbasaur (Grass) against Fire-type trainers on map 0.

**Run 45, seed 10044, 1 badge**

> n1_0 catch for a second body (Bulbasaur is alone at Lv5), then n2_0 trainer for levels, then work toward the pokecenter before the gym boss at the bottom.

**Run 46, seed 10045, 1 badge**

> n3_1 (Hiker trainer, +2 levels, Rock/Ground weak to my Grass Bulbasaur lead) → catch node for 6th Pokemon → work down toward gym, healing at pokecenter before the boss.

**Run 47, seed 10046, 3 badges**

> n6_1 (Ace Trainer, +2 levels, leads to battle+pokecenter) → pokecenter on layer 7 to heal Gyarados (43/82 HP) → gym boss on layer 8. We need levels and healing before the boss.

**Run 48, seed 10047, 1 badge**

> n1_0 catch (get a second Pokemon for insurance), then work down through the map: prioritize catching early, level up at trainers, grab the item at n5_1, use move tutor at n5_3 if useful, heal at pokecenter n7_0 before the gym boss at n8_0. Goal: arrive at the gym with at least 3 Pokemon, all above half HP, with a Grass lead to counter Fire-type trainers on this map.

**Run 49, seed 10048, 0 badges**

> Layer 1: catch at n1_0 to get a second Pokemon (breadth early). Then navigate through layers 2-7, prioritizing pokecenter (+ heal before gym). Layer 8 is the gym boss. Grass lead beats Fire trainers on this map.

**Run 50, seed 10049, 1 badge**

> n1_0 catch for a second body (breadth early), n2_0 trainer for levels, then head toward the gym at the bottom. Mankey (Fighting) leads against Fire-type trainers on map 0. Heal at pokecenter before the gym boss.

