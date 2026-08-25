# anthropic/claude-haiku-4.5 under harness `v7`

This page holds the notes the model kept while it played. A note is whatever the model chose to write down through its `remember` and `revise` tools, so the notebook records what the model thought worth keeping. Some of it was learned in play and some of it the model already knew, and the notebook does not distinguish them.

The route the model planned for each run is on its own page under `plans/`.

## Pass `20260825-110604-23dc`, `--set reasoning=medium`

The pass played 50 runs and averaged 0.80 badges.

### The notebook at the end

1. Kanto map 0: pokecenter at layer 7 revived full team before gym. Strategy: take catches early + items at layer 2, NOT wild battles (notes [8], [11] show wild battles kill Pokemon). Avoid trainers at layer 3+. Use Rare Candy before gym for final level boost.
2. Silver Powder (+40% Bug move damage) is available on map 1 layer 2; valuable for boosting underleveled Bug-type Pokemon like Paras early on.
3. Johto map 3 Scientist (Electric/Poison) killed Lv33 Wartortle despite Water type advantage. Water does not "beat it decisively"—this trainer is dangerously strong. Kanto note may have been wrong; test matchups before trusting old notes across regions.
4. Flying Peck does not reliably beat Bug Catcher on Kanto map 1—I lost both Spearow and Paras despite type advantage. Bug trainers are stronger than their level suggests; avoid leading underleveled Pokemon into them.
5. Trainers are lethal at all levels: full HP + type advantage + rotation available is NOT safe. Rhyhorn Lv9 (100% HP, 28/28) died to Fire trainer with neutral matchup. Avoid trainer battles entirely when possible; they counter matchups deliberately. If forced to fight: lead must be overleveled AND have super-effective move, not just full HP and type advantage.
6. Type advantage alone does not guarantee safety: Hypno Lv47 Psychic died to Bug Catcher despite super-effective matchup. Trainer battles at layer 3+ (carrying mixed teams) can kill Pokemon with favorable types. High levels and type advantage are necessary but not sufficient. Unknown trainers are lethal until proven safe.
7. Hiker trainer (Rock/Ground label) killed Hitmonchan Lv35 at layer 2 map 4, despite Fighting-type advantage. Hiker may have mixed types (possibly Flying/Psychic to counter Fighting). Don't assume tooltip type is the only threat—trainers carry multiple Pokemon with varied coverage. Test lead safety before trusting tooltips alone.
8. Wild battles can kill full-health Pokemon: Dewgong Lv40 (122/122) fainted at layer 2 Sinnoh map 5. Don't assume wild battles are safe just because they're +1 level. They can delete a Pokemon from the team.
9. Bug Catcher trainer at Sinnoh map 5 layer 3 killed Hypno Lv47 despite Psychic type advantage. Trainer mixed-team coverage exceeds expected type matchup. My notes' "favorable matchup = safe" assumption is false. Trainers counter expected matchups deliberately.
10. Move Tutor on Kanto map 0 is at layer 5 n5_0, reachable ONLY from Team Rocket Grunt path (n4_0). Hiker path (n4_1) funnels into catch+item, locking out Move Tutor. Path selection at layer 4 determines Move Tutor access. If forced to take trainer battle, pick the one leading to Move Tutor.
11. Wild battles at layer 3-4 killed high-level leads before gym gauntlet (Squirtle Lv13 fainted layer 4 map 1). Even "safe" wild encounters with team rotation available can delete key Pokemon. Earlier wild battles need higher level buffer or should be skipped if lead is irreplaceable.
12. Wild battles in layers 3-4 trigger auto-catch on victory if you don't explicitly flee. Team must have an open slot or you're forced to release someone. Maintain open slots in early layers if you don't want catch triggers.

### How it grew

| run | seed | notes kept | badges |
|--:|--:|--:|--:|
| 1 | 10000 | 0 | 0 |
| 11 | 10010 | 5 | 1 |
| 21 | 10020 | 11 | 0 |
| 31 | 10030 | 11 | 1 |
| 41 | 10040 | 12 | 0 |
| 50 | 10049 | 12 | 1 |

