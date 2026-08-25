# openai/gpt-oss-120b under harness `v7`, the routes it planned

A plan is the route the model laid out for the map it was standing on, through its `plan` tool. One entry per run, in the order the runs were played.

The notes the model kept are on its own page under `notebooks/`.

## Pass `20260824-152959-2b1e`, `--set reasoning=medium`

The pass played 50 runs and averaged 1.26 badges.

Its best run was seed 10029 at 5 badges.

**Run 1, seed 10000, 1 badge**

> n1_0 catch -> n2_0 trainer (+2 all) -> n2_1 catch -> n3_2 trainer (+2 all) -> n6_1 trainer (+2 all) -> n7_1 pokecenter (heal) -> gym

**Run 2, seed 10001, 1 badge**

> Choose Boy starter (Grass). After starter, target catch node on layer1, then trainer node on layer2, then pokecenter before gym.

**Run 3, seed 10002, 1 badge**

> Take catch n2_0 for a new Pokemon, then item node, then trainer nodes for XP, heal at Pokecenter before gym, then face Brock.

**Run 4, seed 10003, 1 badge**

> Choose Boy starter (Grass Bulbasaur). After starter, aim for a catch node at layer1 that opens a trainer node next, then take the trainer for +2 levels, then visit Pokecenter before the first gym, using Bulbasaur as lead.

**Run 5, seed 10004, 1 badge**

> Pick Boy starter (Grass). After starter, aim for catch node to add a second Pokemon, then trainer node for +2 levels, then Pokecenter before the first gym, using Grass lead to beat early trainers.

**Run 6, seed 10005, 1 badge**

> n1_0 catch, n2_0 trainer (+2), n3_0 trade, n4_0 trainer, n5_0 catch, n6_0 item, n7_1 item, then gym with Bulbasaur lead

**Run 7, seed 10006, 1 badge**

> Pick Boy starter (Grass). After starter, aim for catch node that opens an item node then a trainer node for early XP and item boost. Take trainer for +2 levels, then visit Pokecenter before the first gym to heal. Use Grass lead for early battles.

**Run 8, seed 10007, 1 badge**

> Pick Boy starter (Grass). After starter, aim for layer1 catch node n1_0 (adds depth), then item node, then trainer node for +2 levels, then heal at Pokecenter before the first gym.

**Run 9, seed 10008, 0 badges**

> Choose Boy starter (Grass). Aim for layer1 catch node (n1_0) to add a Rock-type, then layer2 item node for Energy Ball, then trainer node for +2 levels, then Pokecenter before Brock gym.

**Run 10, seed 10009, 1 badge**

> Pick Boy starter, then aim for catch node that opens an item then trainer (early item/XP), then heal at Pokecenter before Brock gym.

**Run 11, seed 10010, 1 badge**

> After trainer n6_1 (Team Rocket Grunt) take the pokecenter (+) to heal, then proceed to the gym B. Lead Bulbasaur (Grass) into the Rock gym.

**Run 12, seed 10011, 1 badge**

> Take wild battle (n3_1) -> trainer (layer3) -> trade (layer4) -> pokecenter (layer7) -> gym

**Run 13, seed 10012, 1 badge**

> Choose Boy (Grass starter) as starter; then aim to catch a Bulbasaur lead, take early catch node for depth, then trainer node for +2 levels, heal at Pokecenter before Brock's gym.

**Run 14, seed 10013, 2 badges**

> Pick Boy starter (Grass). After starter, target the layer1 catch node that opens an item then a trainer for early item and XP. Then take the trainer node for +2 levels, heal at the Pokecenter before the first gym (Brock).

**Run 15, seed 10014, 0 badges**

> Choose Boy starter (Grass). Then on layer1 take catch node n1_0 (adds Bulbasaur), then item node, then trainer node for +2 levels. Heal at Pokecenter before Brock's gym, set Bulbasaur as lead.

**Run 16, seed 10015, 1 badge**

> Choose Boy starter. Target layer1 catch node n1_0 (opens item then trainer) for early item and XP. Then take the trainer node for +2 levels. Heal at Pokecenter before Brock gym. Lead with Bulbasaur (Grass) for type advantage.

**Run 17, seed 10016, 1 badge**

> Choose Boy (Grass starter) as starter. After starter, aim for layer1 catch node n1_0 to add a second Pokemon and gain early item, then take the trainer node for +2 levels before heading to the Pokécenter and finally Brock's gym.

**Run 18, seed 10017, 1 badge**

> Choose Boy starter (Bulbasaur). Aim for layer1 catch node n1_0 to add Bulbasaur, then take the item node, then trainer node for +2 levels. Heal at Pokecenter before the first gym (Brock).

**Run 19, seed 10018, 5 badges**

> Layer2 trainer (Team Rocket) -> set Starmie lead for advantage -> +2 levels; Layer3 catch -> add depth; Layer4 trade -> upgrade Fire lead; Layer7 pokecenter -> heal; then gym with Charmeleon lead

**Run 20, seed 10019, 1 badge**

> n1_0 catch -> n2_0 trainer -> n3_3 trainer -> n4_2 trade -> n5_2 trainer -> n6_1 move tutor -> B gym

**Run 21, seed 10020, 1 badge**

> Choose Boy starter, then catch node n1_0, then item node, then trainer node for XP, then Pokecenter before Brock's gym, lead Bulbasaur into the gym.

**Run 22, seed 10021, 1 badge**

> Pick Boy starter, then target early catch node n1_0 to obtain Bulbasaur, proceed to the item node it opens, then the trainer node for +2 levels, heal at the Pokécenter before Brock's gym.

**Run 23, seed 10022, 0 badges**

> Pick Boy starter (Grass). Aim for early catch node (n1_0) to add Bulbasaur, then take the following item node, then trainer node for +2 levels, then head to Pokecenter before the first gym to heal.

**Run 24, seed 10023, 1 badge**

> Pick Boy starter (Grass). After starter, prioritize any catch node that gives a Grass or Water lead, then item node, then trainer node for +2 levels. Heal at Pokecenter before the first gym if lead HP <30% or after any faint. Always set_lead to the type that counters the upcoming trainer/gym before each battle.

**Run 25, seed 10024, 0 badges**

> Pick Boy starter (Grass). After starter, take the layer1 catch node (n1_0) to add Bulbasaur, then proceed to the item node it opens, then the trainer node for +2 levels. Before the first gym (Brock), heal at the Pokecenter if lead HP <30%, set Bulbasaur as lead (Grass) to counter Rock types.

**Run 26, seed 10025, 1 badge**

> Pick Boy starter (Grass). After starter, target the layer1 catch node that opens an item then a trainer for early XP and item advantage before heading to the gym.

**Run 27, seed 10026, 1 badge**

> Pick Boy starter (Grass). Then aim for the layer‑1 catch node (n1_0) to get a starter, followed by the item node and trainer node for early XP. Visit the Pokécenter before the first gym to heal, then set the best type‑advantage lead before each battle.

**Run 28, seed 10027, 2 badges**

> Pick catch node n2_2 to obtain a Ground-type Pokémon, then take the subsequent trainer node for XP, heal at Pokecenter before the gym, and set the Ground lead for the Electric gym.

**Run 29, seed 10028, 1 badge**

> Pick Boy starter (Grass). Aim to catch a Water-type (Poliwag) early, then take trainer node for +2 levels, heal at Pokecenter before first gym.

**Run 30, seed 10029, 5 badges (best)**

> Set Ivysaur lead, take Fisherman trainer (n2_0) for +2 levels, then proceed to next nodes toward Electric gym; heal at Pokecenter if any lead HP low before gym.

**Run 31, seed 10030, 1 badge**

> Take n2_1 (trainer) for +2 levels, then n3_2 (item) to grab a healing item, then n4_0 (trainer) for extra XP, then head to Pokécenter at layer7 (+) before the final gym.

**Run 32, seed 10031, 1 badge**

> After Brock, take catch node n1_0 now, then aim for trainer nodes on layers 2-3 for +2 levels, grab any item nodes, heal at Pokecenter before Misty gym, keep Bulbasaur as lead for Water gym.

**Run 33, seed 10032, 1 badge**

> Choose Boy starter (Bulbasaur). After starter, aim to catch a Water-type (e.g., Psyduck) at the first catch node to counter Brock and early Fire trainers.

**Run 34, seed 10033, 2 badges**

> Map1: take item node n2_1 for passive boost, then trainer node n2_2 (Fire) for +2 levels, then battle node n3_? for +1 level, then heal at Pokecenter before Water gym.

**Run 35, seed 10034, 1 badge**

> Pick Boy starter, then go to layer1 catch node n1_0 to obtain a Water-type (e.g., Psyduck) for early type coverage, then take the following item node, then trainer node for +2 levels, then heal at Pokécenter before the Brock gym.

**Run 36, seed 10035, 1 badge**

> Choose Boy starter (Bulbasaur). Then take layer1 catch node n1_0 to get Psyduck (Water lead). Proceed to the following item node for early passive item, then trainer node for +2 levels. Visit Pokécenter before Brock gym to heal. Set lead Bulbasaur (Grass) with Miracle Seed to defeat Brock's Rock gym.

**Run 37, seed 10036, 1 badge**

> Pick Boy starter Bulbasaur; then aim for layer1 catch node n1_0 for early item and trainer XP, then heal at Pokecenter before Brock gym.

**Run 38, seed 10037, 1 badge**

> Pick Boy starter; then take catch node n1_0 (early Bulbasaur), then item node, then trainer node for +2 levels; heal at Pokecenter before Brock gym.

**Run 39, seed 10038, 1 badge**

> Pick Boy starter (Bulbasaur). After starter, target the layer1 catch node (n1_0) for early Bulbasaur, then take the subsequent item node, followed by the trainer node for +2 levels, then head to the Pokecenter before the Brock gym to heal and boost HP.

**Run 40, seed 10039, 1 badge**

> Pick Boy starter (Bulbasaur). Aim for layer1 catch node n1_0 to secure Bulbasaur, then take the following item node for a passive item, then trainer node for +2 levels, then head to Pokecenter before Brock gym to heal and level up.

**Run 41, seed 10040, 1 badge**

> Choose Boy starter, then catch node n1_0, then item node, then trainer node for +2 levels, then Pokécenter to heal, then Brock gym.

**Run 42, seed 10041, 2 badges**

> Take item node n5_1 (Miracle Seed), then trade node n6_1, then pokecenter n7_0, then gym B

**Run 43, seed 10042, 0 badges**

> Pick Boy starter, then target catch node n1_0 to obtain Bulbasaur, take the subsequent item node, then trainer node for +2 levels, visit Pokécenter before Brock gym, using Bulbasaur as lead.

**Run 44, seed 10043, 1 badge**

> Choose Boy starter; aim to catch a Water-type (Psyduck) at first catch node, then trainer for +2 levels, then Pokécenter before Brock gym, set Bulbasaur as lead for Brock.

**Run 45, seed 10044, 1 badge**

> Pick Boy starter Bulbasaur, set it as lead. Take layer1 catch node n1_0 for early item, then trainer node n2_0 for +2 levels, then Pokecenter to heal before gym, finally lead Bulbasaur into Brock gym.

**Run 46, seed 10045, 1 badge**

> After catching Diglett (Ground), take item node n2_0 for healing items, then trainer nodes for levels, heal at Pokécenter, set Diglett as lead for Brock gym.

**Run 47, seed 10046, 4 badges**

> Take Fisherman trainer (n4_1) for +2 levels and item, then layer5 items, layer6 trade, layer7 Pokécenter, then Grass gym with Charmeleon fire lead.

**Run 48, seed 10047, 1 badge**

> Choose Boy starter (Bulbasaur). Then aim for layer1 catch node n1_0 to catch a Water-type (e.g., Psyduck) for Brock. After catch, take the trainer node for +2 levels, then the item node. Before the first gym, visit Pokécenter to heal, set lead to type that counters gym.

**Run 49, seed 10048, 4 badges**

> Take Fisherman trainer (+2 levels), then catch node for extra Pokemon, then Pokécenter heal, then set Ivysaur lead for Misty gym.

**Run 50, seed 10049, 1 badge**

> Choose Boy starter (Bulbasaur). Aim for layer1 catch node n1_0 to get a second Pokémon, then trainer nodes for +2 levels each, collect early item, then heal at Pokécenter before the first gym (Brock).

