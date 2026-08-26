# inclusionai/ling-3.0-flash under harness `v8`, the routes it planned

A plan is the route the model laid out for the map it was standing on, through its `plan` tool. One entry per run, in the order the runs were played.

The notes the model kept are on its own page under `notebooks/`.

## Pass `20260825-175951-ad4c`, `--set reasoning=medium`

The pass played 50 runs and averaged 1.02 badges.

Its best run was seed 10016 at 4 badges.

**Run 1, seed 10000, 1 badge**

> n1_0 catch for a second body (Squirtle alone is one faint from end), then n2_0 trainer for levels, n3_1 or n3_2 for more XP, heal at pokecenter before gym, beat Brock.

**Run 2, seed 10001, 1 badge**

> Map 0 plan: Bulbasaur (Grass/Poison) and Tentacool (Water/Poison) are my team. I need to reach the gym at layer 8. Strategy: 1) Level up at trainers on layer 2 (both give +2 levels), 2) Grab items on layer 3, 3) Continue through layers 4-6 trainers for more XP, 4) Heal at pokecenter on layer 7, 5) Beat gym on layer 8. Tentacool's Water STAB handles Fire/Ground gyms; Bulbasaur's Grass handles Water/Ground. I'll lead with the type that matches the gym's weakness.

**Run 3, seed 10002, 2 badges**

> n1_0 catch for a second body (insurance against fainting), then n2_0 trainer for levels, then push down the left side through the map to the gym. The catch at layer 1 is cheap and pays for itself by the second gym.

**Run 4, seed 10003, 1 badge**

> n1_0 catch (add a third Pokemon for insurance on this long 9-layer map), then push down through the map prioritizing: trainer nodes for levels, item nodes for held items, the move tutor M for stronger moves, the pokecenter + before the gym, and the trade $ nodes for stronger Pokemon. The gym is at layer 8. Key priorities: (1) catch a third body at layer 1, (2) grab items and the move tutor, (3) heal at the pokecenter before the gym, (4) lead with Squirtle for Water STAB against Fire-types the gym likely uses.

**Run 5, seed 10004, 1 badge**

> n2_0 (Team Rocket Grunt, Poison Pokemon, +2 levels, leads to battle then item) -> n3_? (item) -> n4_? (unknown) -> n5_? (trainers/x) -> n6_? -> n7_+ (pokecenter) -> n8_B (gym). The Grunt gives levels and a Poison Pokemon catch, which is useful coverage. The item node after could be an Escape Rope or healing item. Prioritize reaching the pokecenter at n7_0 before the gym at n8_B.

**Run 6, seed 10005, 1 badge**

> n1_0 catch for a second body (insurance against fainting), then n2_1 trainer for levels, then continue down the map prioritizing catch nodes early and healing at the pokecenter before the gym.

**Run 7, seed 10006, 0 badges**

> n1_0 (catch) first to get a second Pokemon body for insurance. Then n2_1 (wild battle) for levels. Then n3_1 (trainer) for more XP. Then n4_0 (item) for a held item. Then n5_2 or n5_3 (trainers) for scaling. Then n7_1 (pokecenter) before the gym at n8_0. The catch early is critical — a team of one is one faint from the end.

**Run 8, seed 10007, 1 badge**

> n2_0 (trainer) for levels, then n2_1 (item) for a held item. After that, continue through the map prioritizing pokecenter before the gym. The trainer at n2_0 gives +2 levels which helps early, and the item at n2_1 provides a held item for the lead.

**Run 9, seed 10008, 1 badge**

> n3_2 trainer (Hiker, Rock/Ground, +2 levels) — Squirtle Water resists Rock and is super effective against Ground; this is a safe fight for levels. Then push straight to the gym at layer 8. Avoid the item node n3_3 since healing items should be saved for the gym.

**Run 10, seed 10009, 1 badge**

> n1_0 catch for a second body (insurance against fainting), then n2_1 trainer for levels, then push through to the gym at the bottom. Early catch is cheap insurance; a team of one is one faint from the end.

**Run 11, seed 10010, 1 badge**

> n1_0 catch for a second body (early insurance), then n2_1 item to grab a held item, then push through trainers on deeper layers, heal at pokecenter before the gym, and lead Squirtle into the gym with Bubble STAB.

**Run 12, seed 10011, 1 badge**

> n1_0 catch for a second body (insurance against fainting), then n2_1 trainer for levels, then push through to the gym. Early catch is cheap and gives a backup Pokemon.

**Run 13, seed 10012, 1 badge**

> Pick Squirtle (Water type) as starter. Water resists Fire and Bubble provides reliable STAB. Route plan: n1_0 catch for a second body, n2_1 trainer for levels, skip the item at n3_2, pokecenter n7_0 before the gym. Prioritize reaching the first gym with a type advantage.

**Run 14, seed 10013, 1 badge**

> n1_0 catch for a second body (insurance against fainting), then n2_1 trainer for levels. Skip the item node at n5_0 to save resources for the gym. Heal at n7_1 pokecenter before the gym at n8_0.

**Run 15, seed 10014, 2 badges**

> n3_2 trainer (Gentleman, +2 Levels) to bring Machop closer to the rest of the team, then take the item node that opens next for healing before the gym. Push through to the gym leader at the bottom.

**Run 16, seed 10015, 1 badge**

> n1_0 (catch) first: add a second Pokemon to the team for insurance against fainting. n1_1 (battle) second: level up Squirtle before pushing deeper. After layer 1, prioritize catch nodes and avoid unnecessary trainer fights until the gym. The gym (B) is at layer 8, so I need to build team depth and levels on the way down.

**Run 17, seed 10016, 4 badges (best)**

> n2_1 (trainer +2 levels) to boost team before gym. Team is at Lv26-29 with 4 badges — need every level for the badge 5 gym. After trainer, continue through the map toward the gym at layer 8, healing at pokecenter (+ node) if needed before the boss.

**Run 18, seed 10017, 1 badge**

> n1_0 catch for a second body (insurance against fainting), then push straight to the gym. Avoid optional trainer battles until after the first badge. Heal at the pokecenter before the gym leader.

**Run 19, seed 10018, 1 badge**

> n1_0 catch for a second body (insurance against fainting), n2_1 trainer for levels, skip the item at n3_2, pokecenter n7_0 before the gym.

**Run 20, seed 10019, 1 badge**

> n2_2 (item) at layer 2 to grab a healing item for the gym ahead. Then push down through the map taking trainers (T) for levels. Heal at pokecenter (+) before the gym (B) at layer 8. Goal: arrive at the gym with Squirtle Lv14+, Lickitung Lv13+, Zubat Lv11+.

**Run 21, seed 10020, 1 badge**

> n1_0 catch for a second body (insurance against fainting), n2_1 trainer for levels, skip the item at n3_2, pokecenter n7_0 before the gym.

**Run 22, seed 10021, 1 badge**

> Layer 1: n1_0 (catch) — get a second Pokemon early for insurance; a team of one is one faint from the end. Layer 2: pick the trainer node (T) for levels — trainers give more XP than wild fights. Layer 3: pick the item nodes (i) to stock healing items before the gym. Layer 4-5: push through trainers for levels, avoiding unnecessary fights. Layer 6: the $ trade node if available — a stronger Pokemon pays off. Layer 7: heal at + pokecenter before the gym. Layer 8: B gym leader — arrive with full HP and a type advantage lead.

**Run 23, seed 10022, 1 badge**

> n1_0 catch for a second body (insurance against fainting), n2_1 trainer for levels, then push to the gym. Early catch pays for itself by the second gym.

**Run 24, seed 10023, 1 badge**

> n2_0 catch for a third Pokemon (Diglett already caught, but this node offers another catch option for coverage), n2_1 trainer for levels, then push toward the gym. My plan: catch at layer 2 if a good type appears, otherwise trainer for levels, then item/heal before the gym.

**Run 25, seed 10024, 1 badge**

> n1_0 catch for a second body (insurance against fainting), then n2_1 trainer for levels, then n3_2 trainer for more XP, then n4_3 item (keep for later), then n5_4 trainer, then n6_5 battle, then n7_6 pokecenter before the gym, then B gym leader.

**Run 26, seed 10025, 1 badge**

> n2_0 battle for XP (left side), then n3_1 item, n4_2 trainer for levels, n5_0 item, n6_1 trainer, n7_0 pokecenter heal, then B gym. Prioritize leveling battles and healing before the gym.

**Run 27, seed 10026, 1 badge**

> n1_0 catch for a second body (insurance against fainting), then n2_1 trainer for levels. Skip the item at n3_2 to save turns. Heal at pokecenter before the gym.

**Run 28, seed 10027, 1 badge**

> n1_0 (catch) to add a 4th Pokemon for redundancy — with only 3 Pokemon and one faint ending the run, I need more bodies. The catch node leads to another catch or trainer, so I can keep building. After catching, push through the trainer nodes and use the pokecenter at layer 7 before the gym at layer 8.

**Run 29, seed 10028, 1 badge**

> Catch Rhyhorn (Ground/Rock) for Electric coverage against Lt. Surge. Then push through the map: n1_0 trainer for levels, n2_1 catch or trainer, skip unnecessary items, pokecenter before the gym. Goal: reach Brock (Rock gym) with Squirtle leading (Water beats Rock) and Rhyhorn as a second body for Electric coverage.

**Run 30, seed 10029, 1 badge**

> Start with Squirtle (Water type, strong STAB with Bubble, resists Fire). On the map, scout using what_lies_ahead before committing to any node. Prioritize catching a second Pokemon at layer 1 for team depth. Skip unnecessary trainer fights early to conserve HP and items. Save healing items for the first gym battle. Lead with Squirtle for Water-type matchups against Fire gyms.

**Run 31, seed 10030, 1 badge**

> n1_0 (catch) first - adds a second Pokemon for insurance, notes say "catch at layer 1 costs one turn and pays for itself by the second gym." Then n2_1 (trainer) for levels, then push toward the gym at layer 8. Avoid unnecessary fights early; heal at pokecenter before the gym leader.

**Run 32, seed 10031, 1 badge**

> n4_1 move_tutor to strengthen a Pokemon before the gym, then n5_2 trainer for levels, then n6_2 wild fight for XP, then n7_1 pokecenter to heal before the gym at n8_0.

**Run 33, seed 10032, 0 badges**

> n1_0 catch for a second body (insurance against fainting), then n2_1 trainer for levels, skip the item at n3_2, pokecenter before the gym.

**Run 34, seed 10033, 1 badge**

> n1_0 catch for a second body (insurance against fainting), then n2_1 trainer for levels, then continue down the map toward the gym. A team of one is one faint from the end of the run, so catching early is cheap insurance.

**Run 35, seed 10034, 1 badge**

> n1_0 (catch) first to get a second Pokemon for insurance — a team of one is one faint from the end. Then work through the map layers toward the gym, healing at the pokecenter before the boss.

**Run 36, seed 10035, 1 badge**

> n1_0 catch for a second body (insurance against fainting), then n2_1 trainer for levels. Prioritize leveling Squirtle before the first gym. Heal at pokecenter before gym leader.

**Run 37, seed 10036, 1 badge**

> n1_0 catch for a second body (insurance against fainting), n2_1 trainer for levels, skip the item at n3_2, pokecenter before the gym at layer 7.

**Run 38, seed 10037, 0 badges**

> n1_0 catch for a second body (insurance against fainting), then n2_1 trainer for levels, skip optional item if HP is low, heal at pokecenter before the gym leader.

**Run 39, seed 10038, 1 badge**

> n1_0 (catch) at layer 1 to get a second Pokemon for insurance. Then work down through the map: layer 2 wild fights for levels, layer 3 item/trainer/$ trade as available, layer 5 pokecenter if needed, layer 6 tutors, layer 7 heal before gym, layer 8 B gym leader. The catch at layer 1 costs one turn and pays for itself by the second gym.

**Run 40, seed 10039, 1 badge**

> n1_0 catch for a second body (insurance against fainting), then n2_1 trainer for levels. Skip the item node at layer 5 to preserve resources. Heal at pokecenter n7_0 before the gym at layer 8.

**Run 41, seed 10040, 0 badges**

> n5_0 (item) for safety - I've lost multiple runs running out of healing items before the gym. Then work through layer 6 trainers for levels, layer 7 pokecenter if needed, and reach the gym at layer 8. My 4 Pokemon provide good breadth; prioritize keeping Squirtle healthy as lead with Leftovers sustain.

**Run 42, seed 10041, 1 badge**

> n6_1 wild battle (+1 level) -> layer 7 pokecenter n7_0 to heal fainted Squirtle and Mankey -> B gym leader. Squirtle and Mankey are at 0 HP and cannot fight; only Voltorb and Pinsir are available. Must reach pokecenter before the gym to restore them.

**Run 43, seed 10042, 1 badge**

> n1_0 catch for a second body (insurance), then work down through the map. Prioritize reaching the pokecenter (+) before the gym (B). Avoid unnecessary wild fights that waste HP. The catch at layer 1 costs one turn but pays for itself by the second gym — a team of two is far more survivable than a team of one.

**Run 44, seed 10043, 1 badge**

> n2_0 (trainer) for +2 levels, then n2_1 (item) for a held item. Trainers give more XP than wild battles and the item will help sustain the team through the remaining layers. After layer 2, continue toward the pokecenter before the gym.

**Run 45, seed 10044, 1 badge**

> n1_0 (catch) first to get a second Pokemon for insurance. Then n2_1 (item) to grab a useful held item. Then work down through the map toward the gym, healing at the pokecenter before the boss. Prioritize catching over leveling — a team of two is far safer than one strong Pokemon.

**Run 46, seed 10045, 1 badge**

> n6_1 (battle, +1 level) -> n7_0 pokecenter (heal before gym) -> n8_0 B gym leader. The battle gives +1 level to Exeggcute (lead), and the pokecenter path is critical for healing before the gym. The move tutor (n6_2) only leads to item, cutting off the pokecenter — too risky without a heal before the boss.

**Run 47, seed 10046, 1 badge**

> Layer 2: catch (n2_0) to get a third Pokemon for team insurance. Layer 3: from catch, choose item node to pick up a useful item. Layer 4: avoid trainer if possible, head toward pokecenter. Layer 5-6: grab move tutor or trade if available. Layer 7: heal at pokecenter before gym. Layer 8: gym leader. Priority: catch early, heal before gym, avoid unnecessary trainer fights.

**Run 48, seed 10047, 1 badge**

> At layer 2, I have two options: n2_0 (Wild Battle, +1 level, leads to catch and trainer) and n2_1 (Hiker trainer, +2 levels, Rock/Ground Pokemon, leads to trainer). I will take n2_0 (battle) because: (1) it gives +1 level to Squirtle, keeping it ahead of Drowzee; (2) it leads to a catch node, which is critical for getting a third Pokemon for team depth; (3) the catch node then leads to a trainer, giving more XP. The Hiker trainer at n2_1 gives +2 levels but only leads to more trainers, no catch. I need a catch node soon to build team depth before the gym. My plan is: n2_0 (battle) -> catch -> trainer -> pokecenter before gym.

**Run 49, seed 10048, 1 badge**

> n1_0 (catch) first to get a second Pokemon for insurance. Then n1_1 (battle) for levels. After that, work down through the map: prioritize pokecenter (+ node) before the gym (B node at layer 8). The catch at layer 1 costs one turn but pays for itself by the second gym — a team of two is far safer than one.

**Run 50, seed 10049, 1 badge**

> n7_1 pokecenter first: heal the team before the gym boss. Our notes say "heal before the gym when under half HP" and "under 60% HP with a gym next, heal FIRST." After healing, go to n8_0 (boss) with full HP. The wild battle at n7_0 gives +1 level but risks HP loss before the gym — not worth it when we can heal and enter the boss at full strength.

