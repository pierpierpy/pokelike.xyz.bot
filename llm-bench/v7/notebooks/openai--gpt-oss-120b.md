# openai/gpt-oss-120b under harness `v7`

This page holds the notes the model kept while it played. A note is whatever the model chose to write down through its `remember` and `revise` tools, so the notebook records what the model thought worth keeping. Some of it was learned in play and some of it the model already knew, and the notebook does not distinguish them.

The route the model planned for each run is on its own page under `plans/`.

## Pass `20260824-152959-2b1e`, `--set reasoning=medium`

The pass played 50 runs and averaged 1.26 badges.

### The notebook at the end

1. Boy starter Bulbasaur (Grass) with Miracle Seed at Lv10 defeats Brock's Rock gym alone.
2. Fire trainers early in Kanto are weak to Water lead; use Poliwag or Slowpoke to gain +2 levels.
3. Trainer nodes grant +2 levels; wild battle nodes grant +1 level; take them before gym then heal at Pokécenter.
4. Layer1 catch node n1_0 opens item then trainer; catch first then trainer for +2 levels and item.
5. Choosing n3_1 (wild battle) grants a trade node later, useful to replace low-level Magikarp before the next gym.
6. Hiker trainers use Rock/Ground Pokemon; Water lead (Psyduck) is super-effective, also Fire or Ground leads work.
7. Bug trainer uses Bug Pokemon; lead with Grass (Bulbasaur) for +2 levels.
8. Catch Gastly early; its Ghost/Poison moves counter Sabrina's Psychic gym.
9. Electric gym uses Electric types; lead with Ground (e.g., Diglett) for super-effective advantage.
10. Fire trainer battles can be won with Ground lead (Sandshrew) for +2 levels, preserving Electric lead for Water trainers.
11. Evolve Eevee to Vaporeon for Water coverage before Fire gym.
12. Team Rocket Grunt uses Poison Pokemon; lead with Psychic (Starmie) for super-effective advantage and +2 levels.
13. Trade node ($) at layer 4 swaps low‑level Water (e.g., Magikarp) for a higher‑level Pokémon; do it before Misty gym for stronger lead.
14. If your lead is fainted before a gym, use Sacred Ash to revive it before battling.
15. kanto map 0 layer1 catch node n1_0 opens an item node then a trainer node, giving early item and XP boost.
16. Heal at Pokecenter before any gym if lead HP <30% to ensure lead survival.
17. At kanto map 1 layer1, trainer node gives +2 levels; Fire type, water lead (Psyduck) wins.
18. Catch a Water-type (e.g., Psyduck) early to counter Brock's Rock gym and early Fire trainers.
19. Scientist trainer (Electric/Poison) at layer5 gives +2 levels and opens a trade node; trade low-level Machop for stronger Pokémon before Water gym.
20. Always set the best type‑advantage lead before a battle using set_lead; it costs no turn.
21. If primary lead faints before a gym, switch to a type‑advantage lead (e.g., Grass for Water gym) before battling.
22. If a lead's HP is below ~30% before a gym, use Sacred Ash or heal at Pokécenter to fully restore it before battle.
23. If your Ground lead is fainted before an Electric gym, revive it with Sacred Ash or trade for a higher‑level Ground Pokémon.
24. Fire gym (Blaine) needs Water-type lead; if primary water Pokémon are fainted, use Starmie as lead for super-effective advantage.
25. Scientist trainer (Electric/Poison) – set lead to Sandshrew (Ground) to neutralize Electric; if front is Poison, Grass lead works.
26. At layer 4, choose trainer node before item to gain +2 levels early; item nodes can be taken later.
27. Brock's Rock gym can be beaten with Bulbasaur lead (Grass) at Lv11 with Miracle Seed equipped.
28. Brock's Rock gym can be beaten with a Water-type lead (e.g., Krabby) at Lv15+; no Miracle Seed needed.
29. If your lead is fainted before a gym, use Sacred Ash or trade for a fresh high‑level Pokémon before the gym.
30. If Bulbasaur (Grass) is fainted before Misty gym, heal at Pokecenter first to use it as lead.
31. Teach Bulbasaur Energy Ball at move tutor before Brock gym for higher damage than Magical Leaf.
32. Bulbasaur starter gives a Grass lead that can beat Brock's Rock gym; keep it as lead and consider Miracle Seed later.
33. Miracle Seed on Bulbasaur boosts Grass moves; use it to beat Brock's Rock gym at Lv10.
34. Trade node before a gym can replace a fainted lead with a higher‑level Pokémon, ensuring you have a viable type advantage.
35. kanto map 1 trainer node n4_1 Firebreather gives +2 levels; lead with Water (Krabby) for super-effective win.
36. kanto map 0 layer3 trainer node n3_1 gives +2 levels and an item after battle; prefer it over n3_0.
37. Miracle Seed boosts Grass move power; equip on Bulbasaur to beat Brock's Rock gym at lower level.
38. Water gym (Misty) is weak to Grass; keep Bulbasaur as lead (Lv15+) for +2 level advantage.
39. kanto map 4 item node n2_0 leads to battle then trainer (+3 levels); n2_1 leads to battle then battle (+2 levels). Prefer n2_0 for extra XP before gym.
40. Use Rare Candy on lead before Poison gym to boost level and ensure win.

### How it grew

| run | seed | notes kept | badges |
|--:|--:|--:|--:|
| 1 | 10000 | 6 | 1 |
| 11 | 10010 | 40 | 1 |
| 21 | 10020 | 40 | 1 |
| 31 | 10030 | 40 | 1 |
| 41 | 10040 | 40 | 1 |
| 50 | 10049 | 40 | 1 |

