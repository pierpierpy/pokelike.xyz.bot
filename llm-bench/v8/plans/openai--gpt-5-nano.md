# openai/gpt-5-nano under harness `v8`, the routes it planned

A plan is the route the model laid out for the map it was standing on, through its `plan` tool. One entry per run, in the order the runs were played.

The notes the model kept are on its own page under `notebooks/`.

## Pass `20260825-180055-73cd`, `--set reasoning=medium`

The pass played 50 runs and averaged 0.70 badges.

Its best run was seed 10033 at 2 badges.

**Run 1, seed 10000, 1 badge**

> n2_1 item -> n2_2 catch -> n3_2 trainer

**Run 2, seed 10001, 1 badge**

> route: map0, node0_0 (Boy) selected as lead; then proceed to any early catch on map0 if available, but prioritize healing before any gym encounter; plan to grab the item on map1 before the trainer for a quick team boost, then push toward the gym and heal at pokecenter before the boss.

**Run 3, seed 10002, 0 badges**

> map0: choose BOY; map1: grab item on gym-access path if present before trainer; heal at pokecenter before gym; proceed toward gym.

**Run 4, seed 10003, 0 badges**

> plan: n4_2 catch now to diversify the team; after the catch, take the resulting item next turn to boost the squad before the gym; keep options open for future gyms.

**Run 6, seed 10005, 1 badge**

> plan: map0: choose BOY as starter (n0_0). map1: if there is an item on map 1 before the trainer, take it; map1: look for safe XP opportunities and catches that don’t burn turns; map2: if a Pokecenter is available before the gym, heal there; map3: come to gym ready with a lead that counters the gym type, and set lead before the fight.

**Run 8, seed 10007, 1 badge**

> plan: map0_start -> choose Boy or Girl; then if possible, pick map1 safe XP path with early item pick and heal before gym; reach gym with HP >60%.

**Run 11, seed 10010, 0 badges**

> plan: map0: start with n0_0 (Boy) as starter. After the choice, aim for a safe XP path via n1_0 (catch) and n1_1 (trainer) if HP allows; retreat to pokecenter if needed. If a map1 item is available along the route, grab it before the trainer to boost power. Before the gym, visit Pokecenter to heal; keep HP above 60% before entering the gym. Lead the next fight with a sturdy, reliable starter in slot 0.

**Run 12, seed 10011, 1 badge**

> plan: map0: pick BOY as your player; map0_layer1: catch early for backup body to avoid early wipes; map0_layer2: take safe trainer for XP and for levels; map0_layer3: visit pokecenter before gym to restore HP; map0_layer4: ensure at least 2 healthy Pokemon before gym; map0_layer5: approach gym with strong lead in slot0 that counters gym type; map0_layer6: if possible, grab any early map1 item to boost power as notes suggest; map0_layer7: aim to reach gym with HP above 60% and resources intact before the fight.

**Run 13, seed 10012, 1 badge**

> route: n0_0 start with BOY; n0_1 avoid the first trainer on map0 to preserve HP; n1_0 take any safe early catch if HP is high; n1_1 grab map1 item before trainer if available; n2_0 heal at pokecenter before the gym; lead with the BOY in slot 0 for the gym.

**Run 14, seed 10013, 1 badge**

> plan: start with BOY as starter; map 0: take a safe early route, catch a backup Pokemon if possible, avoid risky fights when HP is low; heal at pokecenter before the gym, keep potions for late map; aim for map progression to the gym, then healer before boss.

**Run 15, seed 10014, 0 badges**

> plan: map0: n0_0 choose BOY as starter and set lead to slot0; n0_1 try to catch an early partner if available to fill the team; n0_2 if HP drops below 60% before any gym, retreat to Pokecenter to heal; n0_3 avoid unneeded trainer fights when HP and resources are low; n0_4 heal at Pokecenter before the gym and ensure lead remains in slot0 for the gym.

**Run 16, seed 10015, 1 badge**

> plan: map0: pick Boy as starter; aim to reach a Pokecenter to heal before any trainer; if an optional map1 item is reachable without delaying the gym, grab it to boost power; ensure the lead in slot0 is strong for the first gym and heal before the gym.

**Run 17, seed 10016, 1 badge**

> map 0 route plan: - node n2_0 (catch) first; take a backup Pokemon to diversify the squad. - after catching, if an early map1 item is accessible on this map, take it before engaging trainers (to power up the team). - keep Bulbasaur as lead; heal before the gym when HP is under ~60% to avoid a wipe. - progress toward the gym by the safest path available; if a trainer offers a safe XP gain with HP full, take it only if it doesn’t jeopardize healing resources. - once the gym approaches, ensure you have full HP and a backup Pokemon in reserve before the boss fight.

**Run 18, seed 10017, 1 badge**

> plan: map0 plan: start at map0 with BOY as starter (n0_0); then take any safe map1 item (n1_0) before the trainer; heal to full before the gym (n2_0); set a strong lead for the first gym (n3_0); if HP is getting low, heal again before the gym; proceed to the gym (n4_0).

**Run 19, seed 10018, 0 badges**

> plan for this map: choose BOY as starter (node 0). After the choice, aim to take safe XP/gear routes on map 0 to secure a strong lead; if an early map1 item is safe and does not delay the gym, grab it; always prioritize a strong lead in slot 0 and heal before the gym when HP is under 60%; save pokecenter visits for the gym encounter to ensure I reach it with HP margin. After securing the first badge, adapt plan to balance the team before the next gym.

**Run 20, seed 10019, 1 badge**

> Plan for map 0: pick Boy as lead; farm XP and gear safely via low-risk trainers and wilds; visit pokecenter before the gym to ensure HP; grab any map1 item only if it does not cost the gym; avoid early risky routes that deplete items and HP; reach the gym with HP > 60% and at least a modest level lead; if a trainer appears too dangerous, retreat to heal and regroup.

**Run 21, seed 10020, 1 badge**

> plan: map0_start -> choose Boy in slot0 (n0_0); n0_1 take safe trainer for XP and test team; n0_2 if HP allows, move toward pokecenter before the gym; n0_3 attempt early map1 item only if it does not cost the gym; final goal: reach gym with lead Boy, heal before gym, then beat boss.

**Run 22, seed 10021, 0 badges**

> Plan: map0 route: n0_0 Pick Boy; n1_0 farm XP and gear on safe wilds/trainers; n2_0 if safe, grab map1 item; n3_0 heal to full before gym; n4_0 lead Boy into gym.

**Run 23, seed 10022, 0 badges**

> route: map0_start with Boy (slot0) -> farm XP via safe wilds and Trainers on map0 -> (if HP < 60%) heal at Pokecenter before gym -> approach Gym Lead (Map0 Boss) with Boy as planned frontliner; grab any early map0 item only if it does not cost the gym; then proceed to gym

**Run 24, seed 10023, 1 badge**

> n3_3

**Run 25, seed 10024, 1 badge**

> plan: catch Drowzee on map 0 to diversify the team and gain a sturdy special attacker; then take safe routes to grind XP on wilds and trainers, heal before the gym, and lead with Bulbasaur. Prefer pokecenter before the gym; avoid risky detours that burn items. This route keeps options open for a stronger squad for the first gym.

**Run 26, seed 10025, 0 badges**

> plan: map0 route for first gym: 1) take catch path at map0 node n3_3 to diversify the team (catch a new mon). 2) proceed to trainer to gain early XP while keeping HP safe. 3) before engaging the gym, heal to full at a pokecenter and stock potions if possible. 4) establish Boy as the lead in slot 0 and keep a reliable, balanced team for the gym. 5) grab any early map0 item if it does not cost the gym and does not burn through crucial resources; avoid high-risk detours. 6) aim to reach the gym with balanced levels and at least one strong backup in case the gym spores require a different type matchup. 7) write notes after the run to remember what worked for future regions.

**Run 27, seed 10026, 1 badge**

> map0: Start with Boy; take the map0 catch path to diversify the team (catch one Pokémon) before engaging the trainer; then challenge the trainer, heal before the gym at the pokecenter, and lead with a reliable starter for the gym. If an early map0 item is safe and does not cost the gym, grab it; otherwise skip. Plan aims to maintain HP above 60% before the gym and stock potions where possible.

**Run 28, seed 10027, 1 badge**

> Plan: map 0 route to start with Boy (n0_0). Take the safe catch/trainer path to build a balanced team before confronting the first gym. If a map 0 item is available that doesn't cost the gym, grab it for early stat boost. After soft XP grind on safe routes and a pokecenter heal, approach the gym with a solid lead. For the lead, prepare Bulbasaur as slot 0 to exploit Grass moves against the first gym type (likely Rock/Fire/etc; Grass often broad). Heal to full before the gym and keep potions handy. This plan prioritizes balancing the team, securing items only when safe, and ensuring a reliable lead for the first gym.

**Run 29, seed 10028, 1 badge**

> route: map0_0_start: pick Boy as starter; map0_1_catch: take the catch path to diversify and gain XP; map0_2_trainer: clear safe trainer encounters for levels; map0_3_pokecenter: heal to full before gym; map0_4_gym: lead with Boy and take the gym.

**Run 30, seed 10029, 1 badge**

> plan: start with Bulbasaur; take a safe XP route on map0 (catch if available to diversify); defeat or bypass the first trainer as needed while farming XP; heal to full at a Pokecenter before the gym; if an early map0 item is available without cost, grab it; lead with Bulbasaur into the first gym; aim to reach the gym with HP comfortably above 60% and stock a Potion before risky fights.

**Run 31, seed 10030, 1 badge**

> plan: map0: take the catch path at node n3_3 to diversify the team before engaging the trainer; after catching, proceed to the trainer and gain XP safety; hit pokecenter before the gym to ensure HP; lead with a healthy Boy in slot 0 for the gym; grab an early map1 item if it does not cost the gym and doesn’t waste turns; otherwise farm XP/gear on safe routes first; keep potions stocked for healing and use them before high-risk fights; overall aim: maximize HP, XP, and coverage before the first gym while keeping options open.

**Run 32, seed 10031, 1 badge**

> route: map0: take the catch path at n3_3 to diversify the team, then engage the trainer, then heal before the gym; bench a strong lead (Bulbasaur) in slot0 with items as needed; grab any map0 item only if it does not cost the gym; aim to reach a Pokecenter before the boss for safety.

**Run 33, seed 10032, 1 badge**

> Plan: map0: take the catch path at node n3_3 to diversify the team, then trainer; heal before gym; bench a strong lead (Bulbasaur) in slot0 with items as needed; grab map0 item only if it costs nothing toward preparing for the gym; reach Pokecenter before the gym to ensure survival.

**Run 34, seed 10033, 2 badges (best)**

> Plan for map0: Pick BOY (Bulbasaur lead) to open. Take the safe catch path early to diversify the team (avoid risky encounters). Then go to trainer, and after catching, heal before the gym. Bench a reliable lead in slot0 (Bulbasaur) with items as needed. If an early map0 item costs nothing toward the gym, grab it; otherwise skip it to preserve resources. Reach Pokecenter before the gym to ensure survival. The overarching rule: farm XP safely on safe routes, stock up on items, then heal before the boss; lead choice is critical for the first gym.

**Run 35, seed 10034, 1 badge**

> plan: map0 -> n2_0 (catch) to diversify the team; then n2_1 (trainer) for safe XP and stronger coverage; after that heal at pokecenter before the gym; keep Bulbasaur as lead and use it for the gym; if a map1 item is cheap and safe, take it before the trainer; otherwise skip; aim to reach Pokecenter before fighting the gym to preserve HP.

**Run 36, seed 10035, 1 badge**

> plan: map0: choose catch path first (diversify team, n3_3). Then take trainer on map0 to gain XP and scouting. Before the gym, heal to full and visit the Pokecenter. Lead Bulbasaur (slot0) for the gym. If a map0 item is free (costs no gym prep), grab it; otherwise skip. Keep options open for safe XP grind and save items for the gym.

**Run 37, seed 10036, 0 badges**

> plan: map0: start by choosing the Boy; take the catch path at n3_3 to diversify the team; then engage the trainer; heal before the gym (pokecenter if needed); bench Bulbasaur as lead before the gym, with items as needed; grab any map0 item only if it does not cost preparing for the gym; ensure a Pokecenter before the gym for survival.

**Run 38, seed 10037, 1 badge**

> Plan: map0: take catch path at n3_3 to diversify the squad, then trainer; heal before gym; bench a strong lead (Bulbasaur) in slot0 with items as needed; grab map0 item only if it costs nothing toward gym prep; reach Pokecenter before the gym.

**Run 39, seed 10038, 0 badges**

> plan: map0 route: n1_0 catch -> n1_1 battle -> pokecenter before gym -> gym; keep Bulbasaur in lead in slot0, and farm XP with safe routes before the gym.

**Run 40, seed 10039, 1 badge**

> plan: map0: pick Bulbasaur as lead (node 0); if possible take a catch path on map0 to diversify the squad; after catching, fight the trainer on map0; heal to full at a Pokecenter before the gym; keep Bulbasaur in slot0 as lead for the gym; grab any map0 item only if it does not delay gym prep; aim to reach Pokecenter before the gym to ensure survival.

**Run 41, seed 10040, 1 badge**

> plan: map0 strategy route: start with Boy; take the early map0 catch path to diversify the team and build safe XP; then proceed to trainer, farm XP and gear as needed, and heal to full at a Pokecenter before the gym; bench a strong lead (Bulbasaur) in slot0 for the first gym; grab any map0 item only if it does not cost prep for the gym; this plan keeps options open and avoids rushing the boss.

**Run 42, seed 10041, 1 badge**

> plan: map0: start with Boy (Bulbasaur) in slot0 as the lead for the first gym. Take safe XP routes and early catch on map0 to diversify the team. Proceed to trainer, then heal before the gym. If an early map0 item costs nothing toward gym prep, take it; otherwise skip it to keep resources for healing and pokecenter. Aim to reach a Pokecenter before the boss and keep Bulbasaur in lead for the first gym. Consider trades only if they don't waste turns or delay gym prep.

**Run 43, seed 10042, 0 badges**

> plan: map0 route: start with Boy (Bulbasaur) in slot0 as lead. Early path: take the catch path at map0 to diversify the team (n3_3 style) to ensure XP and items without risking the gym. Then hit trainer on map0 to grind levels safely. Before the gym, heal to full at pokecenter (if not on map0 already). Keep Bulbasaur as lead for the first gym; only take map0 items if they cost nothing toward gym prep. After trainer, move to a pokecenter if needed, then prepare for the gym with a solid lead and HP/items.

**Run 44, seed 10043, 0 badges**

> plan: map0 route for first gym. 0) start with Boy; 1) take safe XP route on map0 to stock HP and items; 2) pursue diversifying encounters only if they dont cost prep toward the gym; 3) visit Pokecenter before the gym to heal and stock potions; 4) bench a strong lead (Bulbasaur) in slot0 for the first gym; 5) grab map0 item only if it does not cost prep toward the gym; 6) heal before gym if HP under 60%.

**Run 46, seed 10045, 2 badges**

> plan: map0: start with Boy (Bulbasaur) as lead; take the catch path at map0 node n3_3 to diversify the team; after catching proceed to the trainer; heal before the gym; bench a strong lead (Bulbasaur) in slot0 with items as needed; grab early map0 item only if it costs nothing toward gym prep; aim to reach the Pokecenter before the gym to ensure survival and stock HP/items.

**Run 47, seed 10046, 0 badges**

> plan: map0: n1_0 catch first to diversify the team; then n1_1 trainer to farm XP before the gym; heal to full at pokecenter before the boss; keep Bulbasaur in slot0 as lead for the first gym; grab earliest map1 item only if it costs nothing toward gym prep; if HP dips below 60% before gym, heal first.

**Run 48, seed 10047, 1 badge**

> plan: map1: n1_1 (Wild Battle) -> +1 level for Ivysaur; n2_1 (Hiker) -> +2 levels; n3_1 (Gentleman) -> +2 levels; n4_0 (Ace Trainer) -> +2 levels; n5_0 (Catch) -> diversify if safe; then heal at Pokecenter before gym; lead: Ivysaur in slot0 with Weedle/W Weedle backup; goal: reach gym with Lv high and HP full. This route keeps options open and avoids overcommitting on early risky paths.

**Run 49, seed 10048, 0 badges**

> map0 route plan: - take the catch path early to diversify the team (if catch node is available) - after catching, proceed to trainer - heal before the gym - bench a reliable lead for the first gym (prefer Bulbasaur if it appears as starter or can be caught early) - grab an early map0 item only if it costs nothing toward gym prep - reach Pokecenter before the gym to ensure survival and HP restoration - prioritize safe XP routes (wilds and safe trainers) before risking the gym - keep healing before boss as a top priority

**Run 50, seed 10049, 1 badge**

> map0: start with Boy; take catch path to diversify early; trainer fight next; heal before gym; lead Bulbasaur in slot0 for the first gym; reach Pokecenter before the gym; grab map0 item only if it costs nothing toward preparing for the gym; proceed to gym with safe XP routes to build HP and items.

