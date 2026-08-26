# openai/gpt-oss-120b under harness `v8`

This page holds the notes the model kept while it played. A note is whatever the model chose to write down through its `remember` and `revise` tools, so the notebook records what the model thought worth keeping. Some of it was learned in play and some of it the model already knew, and the notebook does not distinguish them.

The route the model planned for each run is on its own page under `plans/`.

## Pass `20260825-175921-48b2`, `--set reasoning=medium`

The pass played 50 runs and averaged 0.98 badges.

### The notebook at the end

1. Bulbasaur (Grass/Poison) is super-effective against Rock-type gym leaders (e.g., Brock). Use Bulbasaur as lead for the first gym.
2. When facing a Hiker trainer (Rock/Ground), set lead to a Water-type Pokémon (e.g., Psyduck) for super-effective advantage and gain +2 levels to that lead.
3. Catching a Water-type early (e.g., Staryu) provides strong coverage against Fire trainers and serves as a backup lead for Water-type gyms.
4. Team Rocket Grunt trainers use Poison‑type Pokemon; a Psychic or Ground lead (e.g., Alakazam or Diglett) has super‑effective advantage, while Grass leads are weak to Poison.
5. Firebreather trainer uses Fire-type Pokemon; a Water-type lead (e.g., Tentacool) wins and grants +2 levels.
6. Misty (Water) gym is weak to Grass (Ivysaur) or Electric leads; set lead to Ivysaur before battling.
7. Miracle Seed held item boosts Grass move damage; equip on any Grass-type lead (e.g., Bulbasaur) before battles where Grass is super-effective.
8. Trainer nodes (e.g., Ace Trainer, Gentleman) grant +2 levels to the lead Pokémon; always take them before a gym if the lead is healthy.
9. Bug Catcher trainers use Bug-type Pokemon; a Grass-type lead (e.g., Bulbasaur) is super-effective and grants +2 levels.
10. At move tutor, teach Bulbasaur ENERGY BALL (Grass) to replace Magical Leaf, maximizing Grass damage with Miracle Seed for the upcoming Water-type gym.
11. Take the wild battle at layer 1 before catching; it gives +1 level to the lead (Bulbasaur) and keeps the catch node available on layer 2, ensuring a stronger lead for early trainers.
12. Hiker trainers (Rock/Ground) can be defeated by a Fighting-type lead (e.g., Mankey) OR a Water-type lead (e.g., Seel) for +2 levels.
13. Sacred Ash fully restores HP and revives fainted Pokémon. Use it before a gym if your lead (e.g., Bulbasaur) is fainted to ensure you have a viable counter.
14. Eviolite on a non‑final stage Pokemon (e.g., Drowzee) gives +50% DEF/Sp.DEF and is valuable before early gyms; take it when available.
15. Set lead before each battle (free action) to ensure the Pokemon with a type advantage leads, greatly increasing win chances.
16. If your lead Pokémon is fainted before a gym, immediately set lead to a healthy team member and go to the next Pokécenter to heal before the gym battle.
17. If any team members are fainted before a gym, go to the Pokécenter first to revive them, ensuring a viable lead for the gym battle.
18. Map 3 (after 3 badges) gym is Grass-type; set a Poison-type lead (e.g., Weezing) for super-effective advantage.
19. Never enter a gym with any team member below 30% HP; use the Pokécenter at layer 7 before the final gym to fully heal.
20. map 1 layer 3 Bug Catcher trainer uses Bug-type Pokemon; a Grass lead (Bulbasaur) wins and grants +2 levels.
21. map 0 layer2 trainer Bug Catcher is weak to Grass lead; set Bulbasaur as lead to gain +2 levels.
22. Heal at Pokecenter before the first gym to ensure all Pokemon are at full HP; entering a gym with low HP leads to unnecessary fainting and loss of badges.
23. Fisherman trainer (water) is weak to Grass leads (e.g., Ivysaur); using a Grass lead yields super-effective advantage and +2 levels. Use this trainer to boost Grass lead before Electric gym.
24. Hiker trainers use Rock/Ground Pokemon; a Fighting-type lead (e.g., Mankey) is super-effective against Rock and safe vs Ground, giving +2 levels.
25. If team has only one healthy Pokemon, prioritize the trade node to obtain a stronger lead before facing a trainer or gym.
26. Officer trainer (Fire-type Pokemon) is best countered by a Water-type lead (e.g., Tentacool or Poliwag) for super-effective advantage and +2 levels.
27. Choosing the Girl starter gives Bulbasaur (Grass/Poison). Set Bulbasaur as lead immediately; its Grass moves are super-effective against the first Rock-type gym (Brock).
28. Shell Bell passive item heals 15% of damage dealt; equip on lead (e.g., Bulbasaur) for extra survivability in trainer battles and gym.
29. Start with Bulbasaur (Grass/Poison) as starter; leads give super-effective advantage vs early Rock-type trainers and gyms (e.g., Brock).
30. Hiker trainers (Rock/Ground) are best countered by Water or Fighting-type leads for +2 levels; ensure such a lead before facing them.
31. At move tutor nodes, teach Bulbasaur ENERGY BALL (Grass) to replace Magical Leaf for stronger damage, especially before Water-type gyms.
32. When presented with item choices before the first gym, choose Expert Belt for the lead Pokémon if its type is super-effective against the gym leader, to double damage on super-effective hits.
33. Use Rare Candy on the lead Water-type (Seel) before the Water-type gym (Misty) to raise it to level 15, ensuring a strong counter if needed, but primarily set Bulbasaur as lead for the gym.
34. Ace Trainer nodes grant +2 levels; set lead to Grass-type (Ivysaur) before taking them to boost for the upcoming Water gym.
35. Expert Belt should be equipped on the Pokémon that will have a super‑effective move against the upcoming gym leader; keep it in the bag until that lead is known, then equip before the gym battle.
36. Catch Diglett early for Ground coverage; useful against Fire gym (Blaine) and Poison gym (Koga).
37. Teach Earthquake (Ground) to Diglett before the Electric-type gym; Diglett as lead will have a strong super-effective move against the gym leader.
38. If you have a Water-type lead, taking the Fire trainer (Officer) for +2 levels is beneficial before the first gym; otherwise avoid the Fire trainer with a Grass lead.
39. Expert Belt gives +100% damage on super-effective hits; equip on the lead before a gym where its type is super-effective for maximum damage.
40. Equip Leftovers on the lead Pokémon before a gym; its passive HP recovery helps keep the lead alive through the battle.

### How it grew

| run | seed | notes kept | badges |
|--:|--:|--:|--:|
| 1 | 10000 | 4 | 1 |
| 11 | 10010 | 32 | 0 |
| 21 | 10020 | 40 | 1 |
| 31 | 10030 | 40 | 1 |
| 41 | 10040 | 40 | 1 |
| 50 | 10049 | 40 | 1 |

