# openai/gpt-oss-120b under harness `v8`, the routes it planned

A plan is the route the model laid out for the map it was standing on, through its `plan` tool. One entry per run, in the order the runs were played.

The notes the model kept are on its own page under `notebooks/`.

## Pass `20260825-175921-48b2`, `--set reasoning=medium`

The pass played 50 runs and averaged 0.98 badges.

Its best run was seed 10033 at 3 badges.

**Run 1, seed 10000, 1 badge**

> n0_0 pick starter (Boy). After starter, aim to catch a second Pokemon early (catch node). Then train via trainers/wild fights to level up. Visit pokecenter before the first gym. Use set_lead to match gym type. Continue breadth early, depth later.

**Run 2, seed 10001, 1 badge**

> n0_0: Choose Boy starter (Bulbasaur). n1_0: Catch a Water-type (e.g., Staryu) to add coverage. n2_0: Fight early trainer for XP and level up. n3_0: Visit Pokecenter before the first gym to heal. n4_0: Set Bulbasaur as lead (set_lead) and take the first gym (Brock) with Grass advantage.

**Run 3, seed 10002, 1 badge**

> Map 0: Choose Boy starter (Bulbasaur) as lead. Aim to catch early Water-type (e.g., Staryu) on layer 1, then train via trainers to reach level ~12 before first gym. Use Bulbasaur lead against Rock gym (Brock).

**Run 4, seed 10003, 0 badges**

> Choose Boy starter (Bulbasaur) as lead. Early layers: prioritize catch nodes to build a 4‑Pokemon team (include a Water type like Tentacool). Use trainer fights for XP, but only after having at least 3 healthy Pokemon. Visit any Pokécenter before the first gym to fully heal. Before each gym, set lead to a type that counters the gym's primary type (e.g., Grass lead for Brock, Water lead for Misty). Keep Revives reserved for gym battles; use Potions for early heals.

**Run 5, seed 10004, 0 badges**

> Start with Boy (Bulbasaur) as starter. Early layers: catch a Bug-type (e.g., Caterpie) to boost Grass coverage and increase team depth. Use early trainers for experience to level Bulbasaur to at least Lv5 before the first gym. Stop at any Pokecenter before the first gym to heal fully. Goal: have at least 4 Pokemon (Bulbasaur + 3 catches) and be fully healed before Brock.

**Run 6, seed 10005, 2 badges**

> Equip Wide Lens on Mankey (lead). Keep Mankey as lead. Layer1: take trainer (T) for XP. Layer2: trainer (T) for more XP. Layer3: move tutor (M) to teach Mankey a stronger Fighting move. Layer4: trainer (T) for XP. Layer5: pokecenter (i) to heal before gym. Layer6: gym (B) battle.

**Run 7, seed 10006, 1 badge**

> Map 1: Choose Scientist trainer (n5_1) for +2 levels (safe). Then aim for a catch node on next layer to add a Water-type (e.g., Staryu) for extra coverage. After that, head to the gym (layer 8) with Bulbasaur as lead. Use Wide Lens passive throughout.

**Run 8, seed 10007, 3 badges**

> layer3 i: take Leftovers; layer4 T: trainer fight with Sandshrew lead (+2 lvl); layer5 T: trainer fight (+2 lvl); layer6 T: trainer fight (+2 lvl); layer7 +: Pokécenter heal Ivysaur; layer8 B: gym battle with Ivysaur lead (Grass) after full heal.

**Run 9, seed 10008, 1 badge**

> n0_0: Choose Boy starter (Bulbasaur) as lead. After starter, aim to catch a Water-type (e.g., Staryu) on layer 1 of map 1, then visit Pokécenter before first gym to heal. Use Potions early, keep Revives for gym battles.

**Run 10, seed 10009, 0 badges**

> 1. Choose Boy starter (Bulbasaur). 2. Early layers: prioritize catch nodes to build a 4‑Pokemon team, targeting a Water‑type (e.g., Staryu) for Fire coverage. 3. Use trainer nodes for XP after catches. 4. Visit Pokécenter right before the first gym to ensure full HP. 5. Set lead to the type that counters the gym (Water lead for Brock's Rock). 6. Keep Revives untouched until after the first gym.

**Run 11, seed 10010, 0 badges**

> Choose Boy starter (Bulbasaur) as lead; set Bulbasaur as lead (free) before any battle. Aim to catch early Grass/Water types to build team depth before first gym (Brock). Heal at first Pokecenter before gym.

**Run 12, seed 10011, 2 badges**

> 1. Choose Boy starter (Bulbasaur) as lead. 2. Early layer: catch a Water-type (Staryu) for Fire trainer coverage. 3. Catch a Bug-type (Paras) for extra Grass coverage. 4. Visit Pokécenter before the first gym to fully heal. 5. Set lead to Bulbasaur before Rock-type trainers and gym. 6. Use Potions for HP, keep Revives for gym battles only. 7. After gym, consider trade for stronger Water lead if needed.

**Run 13, seed 10012, 1 badge**

> Start: choose Boy starter (Bulbasaur) as lead. After starter, aim to catch a Water-type Pokemon on early catch node to add coverage. Prioritize trainer nodes for XP before first gym. Visit Pokecenter before the first gym to fully heal. Use set_lead to ensure Bulbasaur leads against Rock-type gym (Brock).

**Run 14, seed 10013, 2 badges**

> Map1 plan: layer0 start -> layer1 catch (add 5th Pokemon) -> layer2 catch two more (reach 6 total) -> layer3 take trainer (weak to our lead) then unknown (skip) -> layer4 take move tutor to teach Ivysaur Energy Ball if needed, then trade if available -> layer5 catch one for depth, skip unknown -> layer6 trainer (Rock/Ground) using Water lead Staryu for XP, then move tutor for Staryu -> layer7 take item (Eviolite) and equip on Ivysaur -> layer8 gym (Water) set lead Ivysaur (Grass) with Miracle Seed and Eviolite.

**Run 15, seed 10014, 2 badges**

> Layer0: catch Drowzee (lead). Layer1: trainer Firebreather for +2 levels. Layer2: catch Psyduck. Layer3: trainer Team Rocket Grunt (+2 levels). Layer4: move tutor to boost a move. Layer5: item node after tutor. Layer6: Pokécenter to heal before final gym. Layer7: gym battle.

**Run 16, seed 10015, 1 badge**

> Pick BOY (Bulbasaur starter). After starter, aim to catch a Water-type (e.g., Staryu) early for Fire coverage, then hit trainer nodes that give XP and possible catches. Use Pokecenter before first gym to fully heal. Set lead before each battle to exploit type advantage.

**Run 17, seed 10016, 1 badge**

> Start with Bulbasaur. Early layers: prioritize catch nodes to add Paras (Grass/Bug) and a Water catch (Staryu) for coverage. Take trainer nodes for XP after catches. Visit Pokecenter before the first gym to fully heal. Set Bulbasaur as lead for Brock (Rock gym).

**Run 18, seed 10017, 1 badge**

> Choose Girl starter (Bulbasaur). Early layers: aim to catch Paras (extra Grass coverage) then take the Bug Catcher trainer (use Bulbasaur lead for +2 levels). Visit the Pokécenter before the first gym to fully heal. Catch a Water-type (Staryu or Horsea) before the Water gym, then heal again. Set appropriate lead (Bulbasaur for Rock gym, Water lead for Fire trainers). Prioritize healing and team depth before each gym.

**Run 19, seed 10018, 0 badges**

> 1) Choose Girl starter (Bulbasaur) as lead. 2) Aim to catch Paras (Bug/Grass) early for extra Grass coverage. 3) Take early trainer nodes for XP and level-ups, using Bulbasaur as lead. 4) Visit Pokécenter before the first gym to fully heal. 5) Set Bulbasaur (or Grass lead) before battling Brock (Rock gym). 6) After gym, consider catching a Water-type (e.g., Staryu) for later Fire trainers.

**Run 20, seed 10019, 1 badge**

> Choose Girl starter (Bulbasaur). Early layers: prioritize catch nodes to build team depth (aim for >=4 Pokemon). Take trainer nodes that grant +2 levels, especially those weak to Grass. Visit any Pokécenter before the first gym to fully heal. Before each battle, set_lead Bulbasaur (or appropriate type) for type advantage. Skip items unless they are passive boosts needed later.

**Run 21, seed 10020, 1 badge**

> Start with Girl (Bulbasaur). Early layers: prioritize catch nodes to build team depth (aim for Water-type like Staryu). Take trainer nodes that give +2 levels if Bulbasaur leads (e.g., Bug Catcher, Hiker). Grab any passive items (Wide Lens) before layer 5. Visit Pokécenter before the first gym to fully heal. Use set_lead to keep Bulbasaur as lead for rock-type trainers and gyms.

**Run 22, seed 10021, 1 badge**

> Start with Girl (Bulbasaur). Early layers: prioritize catch nodes to add a second Pokemon (prefer Water-type if available). Then take trainer nodes for +2 levels each, using Bulbasaur as lead to beat Rock/Hiker trainers. Before the first gym, visit the Pokécenter to fully heal. Set Bulbasaur as lead before the gym (Rock-type).

**Run 23, seed 10022, 1 badge**

> Choose Girl starter (Bulbasaur). After starter, aim to catch a Water-type early (layer 1) for coverage, take trainer nodes for XP, visit Pokécenter before the first gym, and always set lead to a type advantage before battles.

**Run 24, seed 10023, 1 badge**

> Choose Girl starter (Bulbasaur). After starter, aim to catch a Water-type early (layer 1) for coverage. Then take trainer nodes for XP and level-ups, prioritizing those that grant +2 levels. Visit any Pokecenter before the first gym to fully heal. Set Bulbasaur as lead for Rock-type gym battles. If a Water gym appears later, switch lead to a Water-type (e.g., Psyduck).

**Run 25, seed 10024, 0 badges**

> n0_0: choose Girl starter (Bulbasaur). After starter, aim to catch Water-type at early layer, train via trainers, heal at Pokecenter before first gym, set lead appropriately.

**Run 26, seed 10025, 0 badges**

> n0_0: choose GIRL starter (Bulbasaur) as lead. Aim to catch a Water-type early (layer 1 catch) for coverage, then visit Pokecenter before first gym, then trainer nodes for XP, keep lead Bulbasaur for Rock gyms, switch to Water lead for Misty later.

**Run 27, seed 10026, 1 badge**

> Start: choose Girl starter (Bulbasaur) as lead. After starter, aim to catch a Water-type early (e.g., at first catch node) to cover Fire gyms. Prioritize trainer nodes that grant +2 levels to lead before any gym. Visit Pokécenter before first gym to fully heal. Set lead before each battle using set_lead. Keep items like Wide Lens for damage boost if encountered.

**Run 28, seed 10027, 1 badge**

> Start: choose Girl (Bulbasaur) as starter. Early layers: aim to catch a Water-type (e.g., Staryu) at first catch node, then take trainer node for +2 levels, then visit Pokécenter before the first gym to fully heal. Set Bulbasaur as lead for Rock-type trainers, switch to Water lead for Water gyms. Keep items for later.

**Run 29, seed 10028, 0 badges**

> n0_1 choose Girl starter (Bulbasaur). After starter, aim for early catch node (layer1) to obtain a Water-type (e.g., Staryu) for coverage. Take trainer nodes (Bug Catcher, Hiker, etc.) that grant +2 levels to the lead. Visit the Pokécenter before the first gym to fully heal the team. Before each battle, use set_lead to put a Pokemon with a type advantage in slot 0. Avoid using the Master Ball early. If a low‑level wild Pokémon appears before any level‑up or healing, Run instead of Fight.

**Run 30, seed 10029, 0 badges**

> Start: choose Girl (Bulbasaur). After starter, prioritize catching a Water-type at early catch node (layer 1) for coverage. Then take trainer nodes to gain +2 levels for lead. Visit Pokécenter before any gym to fully heal. Use set_lead to put the type‑advantage Pokémon in slot 0 before each battle. Skip items that don't boost early damage unless needed.

**Run 31, seed 10030, 1 badge**

> Start with Girl starter (Bulbasaur). Early layers: prioritize catch nodes to add a second Pokemon for backup. Then take trainer nodes to gain +2 levels on the lead. Visit any Pokécenter before the first gym to fully heal. Set Bulbasaur as lead before any Rock-type trainer or gym (Brock). Keep items for later use.

**Run 32, seed 10031, 1 badge**

> Choose Girl starter (Bulbasaur). Early layers: aim for catch node that yields Water-type (e.g., Staryu) to cover upcoming Water gym. Take trainer nodes for +2 levels on lead. Visit Pokecenter before first gym to fully heal. Set lead to Bulbasaur (Grass) for Rock-type trainers, switch to Water lead for Water gym. Prioritize items that boost Grass or Water moves.

**Run 33, seed 10032, 0 badges**

> 1) Choose Girl starter to get Bulbasaur (Grass/Poison) as lead. 2) Early layers: prioritize catch nodes that yield Water-type Pokémon (e.g., Goldeen, Staryu) for coverage against Fire and later Water gyms. 3) Take trainer nodes where Bulbasaur has a super‑effective advantage (Rock/Ground trainers) to gain +2 levels to the lead. 4) Visit any Pokécenter before the first gym to fully heal and revive fainted members. 5) Before each battle, use set_lead to put the Pokémon with type advantage in slot 0 (free action). 6) If team size is low, consider trade nodes to obtain a stronger lead before a gym. 7) Keep healing items (Potions, Revives) for gym battles; use them only on critical HP drops. 8) After the first gym, repeat catch‑trainer‑heal cycle to build a balanced 3‑4 Pokémon team before tackling later gyms.

**Run 34, seed 10033, 3 badges (best)**

> n7_0 (Pokecenter) -> heal full team; then B (gym) with Psyduck lead (Water) neutral to Water gym. Prioritize healing over unknown question node.

**Run 35, seed 10034, 0 badges**

> n0_0: Choose Girl starter (Bulbasaur) as lead; set Bulbasaur as lead (free). This gives Grass/Poison type, super-effective vs early Rock trainers and gyms. Then proceed to next map.

**Run 36, seed 10035, 3 badges**

> At map 3 (3 badges) aim for Grass-type gym. Lead Weezing (Poison) for super-effective advantage. Choose trainer Bug Catcher (node n5_1) to give +2 levels to Weezing. After that, take the subsequent catch node to add a backup Pokemon. Then proceed to the Pokécenter at layer 7 to fully heal before the gym. Finally, keep Weezing as lead into the gym.

**Run 37, seed 10036, 2 badges**

> 1) Choose Girl starter (Bulbasaur) as lead. 2) Aim to catch a Water-type (e.g., Squirtle or Staryu) on early catch nodes for coverage against Rock trainers. 3) Prioritize trainer nodes that give +2 levels to the lead, especially those weak to Grass (Bug Catcher) or Water (Hiker). 4) Visit Pokécenter before the first gym to fully heal. 5) Set lead to the Pokémon with type advantage before each battle (use set_lead free action). 6) Keep Rare Candy for post‑first‑gym boost, not early use.

**Run 38, seed 10037, 0 badges**

> Map 0 plan: 1) Choose the Girl starter to get Bulbasaur (Grass/Poison) as lead for early Rock-type trainers. 2) On layer 1, take the catch node to obtain a Water-type Pokémon (e.g., Poliwag) for coverage against later Water gyms. 3) On layer 2, take a trainer node (preferably Bug Catcher) to gain +2 levels for the lead. 4) On layer 3, visit the Pokécenter to fully heal before the first gym. 5) Proceed to the gym node with Bulbasaur as lead (Grass beats Rock).

**Run 39, seed 10038, 1 badge**

> Start: choose Girl starter (Bulbasaur). After starter, aim to catch a Water-type (e.g., Poliwag) on the first catch node, then take a trainer node for +2 levels, then visit the Pokécenter before the first gym to fully heal. Set Bulbasaur as lead into the Rock-type gym (Brock).

**Run 40, seed 10039, 2 badges**

> Layer1: take wild battle (n1_1) to +1 level Magnemite. Layer2: trainer node (n2_2) for +2 levels; set lead to counter its type. Layer3: catch node (n3_0) to add a Grass-type backup for upcoming Water gym. Layer4: if item or Pokécenter appears, take it to heal before gym. Then proceed to gym with Magnemite (Electric) as lead for Water-type Misty.

**Run 41, seed 10040, 1 badge**

> Layer7: go to Pokecenter (n7_0) to revive Bulbasaur and fully heal team. After healing, set Bulbasaur as lead (slot 2) for the Rock-type gym at layer8. Then battle gym with Grass lead.

**Run 42, seed 10041, 0 badges**

> Start with Girl starter (Bulbasaur). After starter, aim to catch a Water-type early (if available) to cover Water gyms. Prioritize trainer nodes for +2 level boosts, especially those weak to Grass (e.g., Bug Catcher). Visit Pokécenter before the first gym to fully heal. Set Bulbasaur as lead for the first Rock-type gym (Brock).

**Run 43, seed 10042, 0 badges**

> Start with Girl starter (Bulbasaur) as lead. Immediately set lead to Bulbasaur (free). Aim to catch a Water-type early (e.g., Psyduck) on the first catch node to cover Rock/Hiker trainers. Prioritize trainer nodes that give +2 levels to Bulbasaur before the first gym. If a Pokécenter appears before the first gym, heal to full. Keep a backup slot open for a second Grass or Water lead. Only take item nodes if they are passive (e.g., Miracle Seed) that boost Bulbasaur for upcoming Water gym.

**Run 44, seed 10043, 1 badge**

> n0_0: choose GIRL starter (Bulbasaur) as lead; n1_*: aim to catch a Water-type early (e.g., Psyduck) for Hiker counters; prioritize Pokécenter before first gym; use lead swaps before each trainer/gym based on type advantage.

**Run 45, seed 10044, 1 badge**

> Map 0: Choose Girl starter (Bulbasaur) as lead. No other nodes on this map. Bulbasaur provides super-effective advantage vs early Rock-type trainers and Brock gym.

**Run 46, seed 10045, 2 badges**

> Choose Girl starter (Bulbasaur). Immediately set Bulbasaur as lead. Aim to catch a Water-type (e.g., Psyduck) on early catch node for coverage. Use trainer nodes (Hiker, Bug Catcher) to level up Bulbasaur and Water lead (+2 levels each). Visit Pokécenter before first gym (Brock) to ensure full HP. Lead Bulbasaur into Brock's Rock-type gym for super-effective win.

**Run 47, seed 10046, 1 badge**

> n0_0: Choose Girl starter (Bulbasaur). After starter, head to Pokecenter (if available) to heal. Aim to catch a Water-type early (e.g., Staryu) for coverage. Prioritize trainer nodes that give +2 levels to Bulbasaur before the first gym (Brock). Ensure Bulbulas lead before rock gym.

**Run 48, seed 10047, 1 badge**

> Start: choose Girl starter (Bulbasaur). set_lead 0 (Bulbasaur). Early layers: aim to catch a Water-type (e.g., Poliwag) at catch node, then take trainer nodes for +2 levels to Bulbasaur. Visit Pokécenter before first gym (Brock) to fully heal. Set lead Bulbasaur before gym (Rock type).

**Run 49, seed 10048, 1 badge**

> n0_0 start -> n1_1 wild (+1) -> n2_1 wild (+1) -> n3_1 trade (swap for +3 lead) -> n4_0 question (choose move_tutor) -> move_tutor (teach ENERGY BALL) -> trainer (+2 levels) -> n5_0 trainer (gain more levels) -> n6_0 ? -> n7_0 i (item) -> n8_0 B (gym). Goal: get strong Grass lead and heal before gym.

**Run 50, seed 10049, 1 badge**

> n0_1: Choose Girl starter (Bulbasaur). Immediately set lead to Bulbasaur (free). Next aim: locate Pokécenter on layer 1 to fully heal before first gym. Plan to catch a Water-type (e.g., Squirtle) on layer 2 for backup, then head toward the first gym (Brock) with Bulbasaur as lead.

