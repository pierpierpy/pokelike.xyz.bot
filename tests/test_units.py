"""Fast tests: no browser, no network, no game copy needed."""

from __future__ import annotations

import pathlib

import pytest

from pokelike.assets.mirror import _valid_content
from pokelike.bot import available, create
from pokelike.bot.base import Bot
from pokelike.core import render
from pokelike.stats import format_summary, record, recent, summary

# --------------------------------------------------------------- mirror


SPA_SHELL = b"<!DOCTYPE html><html>"


@pytest.mark.parametrize(
    "data,suffix,expected",
    [
        (b"\x89PNG\r\n\x1a\n", ".png", True),
        (SPA_SHELL, ".png", False),           # the case that once filled the mirror with junk
        (b"\xff\xd8\xff\xe0", ".jpg", True),
        (b"ID3\x04", ".mp3", True),
        (SPA_SHELL, ".mp3", False),
        (b"", ".png", False),
        (b"body { }", ".css", True),
    ],
)
def test_recognises_valid_files(data, suffix, expected):
    assert _valid_content(data, suffix) is expected


# ------------------------------------------------------------------ bot


def test_every_bot_on_disk_defines_exactly_one_bot():
    """Each folder under `bots/` must load and define one Bot subclass.

    A bot is loaded from a directory rather than imported from a registry, so
    nothing checks it until something tries to play it. This is that check: a
    folder that will not load is a bot nobody can run, including its author.

    It stops at the CLASS on purpose. Building one is allowed to need things a
    test does not have — the LLM bot refuses to construct without credentials,
    which is deliberate and right.
    """
    from pokelike.bot.catalogue import BOTS, available as on_disk, load_class

    names = on_disk()
    assert names, "bots/ has no bots in it"
    for name in names:
        cls = load_class(BOTS / name / "bot.py")
        assert issubclass(cls, Bot), f"{name} does not inherit from Bot"


def test_the_baseline_is_always_available():
    """`random` must build with no bots/ folder at all: `compare()` defaults to it."""
    assert "random" in available()
    assert isinstance(create("random", seed=1), Bot)


def test_the_sarsa_bot_freezes_exactly_the_features_it_was_trained_on():
    """The copy in `bots/sarsa-v2/bot.py` must stay identical to the training code.

    Weights are a plain list of numbers: index 43 only means `mon_new_type`
    because `feature_names()` says so. Insert one feature on the training side
    and every index after it silently points somewhere else, so the same file of
    weights becomes a different policy — including policies already on the
    leaderboard.

    If this fails, the fix is to bump `FEATURES_VERSION` and retrain, never to
    quietly paste the new names across.
    """
    from experiments.sarsa.features import feature_names as trained_on

    from pokelike.bot.catalogue import load_class

    frozen = load_class(pathlib.Path("bots/sarsa-v2/bot.py")).__module__
    import sys

    assert sys.modules[frozen].feature_names() == trained_on()


# Every branch of `features()`, as states rather than as names: a map node with
# its crosses and its lookahead, both Pokemon cards, the item screen, the two
# screens that list the team and mean opposite things, and a tutor offer. Built
# by hand because this has to stay a fast test — no browser, no game copy.
def _pin_states():
    def mon(uid, name, level, hp, max_hp, types, atk, item=None, move=None):
        return {
            "uid": uid, "species_id": uid, "name": name, "level": level,
            "hp": hp, "max_hp": max_hp, "types": types,
            "base_stats": {"hp": 45, "atk": atk, "def": 49, "speed": 45,
                           "special": 65, "spdef": 65},
            "move_tier": 0, "item": item, "item_id": item, "item_desc": None,
            "move": move or {"name": "Tackle", "power": 40, "type": types[0],
                             "special": False},
            "mega_stone": None, "shiny": False,
        }

    def board(current):
        return {
            "nodes": [
                {"id": "n0_0", "kind": "start", "layer": 0, "col": 0},
                {"id": "n1_0", "kind": "catch", "layer": 1, "col": 0},
                {"id": "n1_1", "kind": "trainer", "layer": 1, "col": 1},
                {"id": "n2_0", "kind": "pokecenter", "layer": 2, "col": 0},
                {"id": "n2_1", "kind": "boss", "layer": 2, "col": 1},
            ],
            "edges": [["n0_0", "n1_0"], ["n0_0", "n1_1"],
                      ["n1_0", "n2_0"], ["n1_1", "n2_1"]],
            "current": current,
        }

    base = {
        "screen": "map-screen",
        "run": {"map": 2, "badges": 1, "anyone_fainted": True},
        "team": [mon(1, "Bulbasaur", 7, 10, 23, ["Grass", "Poison"], 49, "leftovers"),
                 mon(2, "Charmander", 9, 22, 22, ["Fire"], 62, None,
                     {"name": "Ember", "power": 40, "type": "Fire", "special": True}),
                 mon(3, "Psyduck", 5, 0, 18, ["Water"], 52)],
        "bag_items": [{"id": "potion", "name": "Potion"}],
        "offered_moves": {"0": {"name": "Energy Ball", "power": 90,
                                "type": "Grass", "special": True}},
        "type_items": {"Fire": "charcoal", "Water": "mystic_water",
                       "Grass": "miracle_seed", "Normal": "silk_scarf"},
        "map": board("n0_0"), "can_reorder": True, "steps": 5,
        "actions": [{"kind": "node", "id": "n1_0", "node": "catch", "layer": 1, "col": 0},
                    {"kind": "node", "id": "n1_1", "node": "trainer", "layer": 1, "col": 1}],
    }

    def buttons(screen, labels):
        return [{"kind": "element", "idx": i, "label": text, "layer": screen}
                for i, text in enumerate(labels)]

    screens = {
        "catch-screen": ["Psyduck Lv. 4 WATER SP.A 10 SPE 9 HP 18 DEF 8 50 PWR",
                         "Onix Lv. 6 ROCK GROUND ATK 45 HP 35 DEF 60 40 PWR", "SKIP"],
        "starter-screen": ["Bulbasaur Lv. 5 GRASS POISON HP 19 ATK 12 DEF 12 40 PWR",
                           "Charmander Lv. 5 FIRE HP 18 ATK 13 DEF 10 40 PWR ★",
                           "Squirtle Lv. 5 WATER HP 20 ATK 11 DEF 14 40 PWR"],
        "item-screen": ["Charcoal +40% Fire damage", "Moon Stone evolves",
                        "Leftovers heals", "Choice Band +50% ATK", "Keep in bag"],
        "item-equip-modal": ["Bulbasaur", "Charmander", "Psyduck", "Cancel"],
        "swap-screen": ["Bulbasaur", "Charmander", "Psyduck"],
        "move-tutor-screen": ["→ ENERGY BALL : Bulbasaur Lv7", "SKIP"],
        "trainer-screen": ["FIGHT"],
    }

    out = [base, {**base, "map": board("n1_1")}]
    out += [{**base, "screen": s, "actions": buttons(s, labels)}
            for s, labels in screens.items()]
    # A team of one and nothing decided yet: every `or []` fallback at once.
    out.append({"screen": "map-screen", "run": {}, "team": [],
                "actions": base["actions"], "map": board("n0_0"),
                "can_reorder": False})
    return out


@pytest.mark.parametrize("frozen_bot", ["bots/sarsa-v2/bot.py",
                                        "experiments/drrn/bot.py"])
def test_a_frozen_feature_copy_computes_the_same_vector(frozen_bot):
    """The copies must agree on the NUMBERS, not only on the names.

    The test above compares `feature_names()`, which catches an inserted or
    reordered feature and misses a changed one: rescale `mon_power` by 100 on one
    side and both lists still match while every weight that reads it means
    something else.

    It matters most for `experiments/drrn/`, where the two halves of one
    experiment sit on opposite sides of the copy — `collect.py` and `train.py`
    import the training features, `bot.py` carries the frozen ones — so a drift
    fits one feature map and benchmarks another. Both sides keep 100 features and
    nothing raises: the only symptom is a benchmark number that means nothing.
    """
    import sys

    from experiments.sarsa.features import groups as trained_on

    from pokelike.bot.catalogue import load_class

    frozen = sys.modules[load_class(pathlib.Path(frozen_bot)).__module__]
    assert frozen.feature_names() == trained_on.feature_names()

    compared = 0
    for state in _pin_states():
        options = trained_on.reorder_options(state)
        assert options == frozen.reorder_options(state), "the reorder options differ"
        for action in [*state["actions"], *options]:
            assert frozen.features(state, action) == trained_on.features(state, action), (
                f"{frozen_bot} computes a different vector on "
                f"{state.get('screen')} for {action}"
            )
            compared += 1
    assert compared > 40, "the sweep stopped covering the branches it was built for"


def test_new_bot_writes_something_that_loads(tmp_path):
    """Both templates, because they break differently.

    The LLM one is full of JSON — tool schemas are literal braces — and the
    scaffold used `str.format`, so adding a commented-out tool example to the
    template made `new-bot` die with a KeyError about a JSON key. A template is
    only text until someone runs it.
    """
    from pokelike.bot.catalogue import load_class
    from pokelike.bot.llm import LLMBot, LLMConfig
    from pokelike.arena.scaffold import new_bot

    plain = load_class(new_bot("probe-plain", tmp_path) / "bot.py")
    assert plain(seed=0).act({"actions": [{}, {}], "team": []}) in (0, 1)

    llm = load_class(new_bot("probe-llm", tmp_path, llm=True) / "bot.py")
    assert issubclass(llm, LLMBot) and llm.config.prompt
    assert "play" in [t["function"]["name"] for t in llm.tools(llm)]


def test_every_bot_can_actually_be_recorded(tmp_path, monkeypatch):
    """The last five seconds of a benchmark, exercised without the fifty runs.

    `artifacts()` and `record_result` only run after a COMPLETE benchmark, so
    nothing reached them for minutes at a time and three separate breakages sat
    there unseen: a relative import in a recovered bot, an artifact copied onto
    itself now that a bot's folder IS its archive rather than being copied into
    one, and a NameError in the line that lists what was written.

    Recording into tmp_path rather than bots/, so running the tests never files
    a result.
    """
    import shutil

    from pokelike.bot.catalogue import BOTS, available as on_disk, load_class
    from pokelike.arena.leaderboard import fingerprint, load_results, record_result

    for var, val in (("FW_ENDPOINT", "https://x.invalid"),
                     ("FW_TOKEN", "t"), ("MODEL_ID", "m")):
        monkeypatch.setenv(var, val)

    fake = {"summary": {"runs": 50, "badges_mean": 1.0}, "seeds": [1], "runs": []}
    for name in on_disk():
        shutil.copytree(BOTS / name, tmp_path / name,
                        ignore=shutil.ignore_patterns("__pycache__"))
        bot = load_class(tmp_path / name / "bot.py")()
        # The call that was never made: a bot may declare artifacts, and a
        # relative import inside artifacts() survives every other check.
        assert isinstance(bot.artifacts(), list), f"{name}.artifacts() is not a list"
        d = record_result(name, fake, bot, tmp_path)
        assert (d / "result.json").is_file(), f"{name} recorded nothing"

    rows = {r["bot"]: r for r in load_results(tmp_path)}
    assert len(rows) == len(on_disk())
    for name, r in rows.items():
        assert not r["stale"], f"{name} is stale the moment it is written"
        assert not r["unverified"], f"{name} was written without a fingerprint"
        assert r["fingerprint"] == fingerprint(tmp_path / name)


def test_a_bot_is_measured_where_it_lives(tmp_path):
    """`--bot <path>` loads the bot from any folder — an experiment's, usually.

    The point is that measuring a candidate never requires moving it, and above
    all never requires wearing another bot's name: you benchmark the folder you
    are working in, and only a bot brought into bots/ the standard way is ever
    recorded.
    """
    from pokelike.bot import create

    (tmp_path / "bot.py").write_text(
        "from pokelike.bot.base import Bot\n"
        "class MineBot(Bot):\n"
        "    name = 'mine'\n"
        "    def act(self, state): return 1\n",
        encoding="utf-8",
    )
    bot = create(str(tmp_path))
    assert bot.act({"actions": [{}, {}]}) == 1
    assert create(str(tmp_path / "bot.py")).name == "mine"
    with pytest.raises(KeyError):
        create(str(tmp_path / "empty"))


def test_a_trained_net_and_the_bot_that_plays_it_agree():
    """The shipped forward pass must match the one that produced the weights.

    A net is fitted with numpy and played by a bot written in plain Python, so
    that a submission needs no numeric dependency. Two implementations of the
    same arithmetic is exactly the kind of split that drifts without saying so:
    the bot would keep playing, just a different policy from the one measured.

    Skipped where numpy is absent — it belongs to the experiments group, not to
    the package.
    """
    numpy = pytest.importorskip("numpy")

    from experiments.drrn.agent import QNet, densify

    from pokelike.bot.catalogue import load_class

    net = QNet(24, (8, 8), seed=3)
    weights = pathlib.Path("experiments/drrn/artifacts/weights.json")
    if not weights.is_file():
        pytest.skip("no trained net on disk")
    net = QNet.load(weights)
    bot = load_class(pathlib.Path("experiments/drrn/bot.py"))(seed=0)

    rng = numpy.random.default_rng(0)
    worst = 0.0
    for _ in range(50):
        k = int(rng.integers(1, 12))
        idx = rng.choice(net.n_in, size=k, replace=False)
        sparse = {int(i): float(v) for i, v in zip(idx, rng.normal(0, 1, k))}
        a = float(net.forward(densify(sparse, net.n_in)[None, :])[0])
        worst = max(worst, abs(a - bot.q(sparse)))
    assert worst < 1e-9, f"numpy and the bot disagree by {worst:.2e}"


def test_the_two_sarsas_are_two_different_policies():
    """v1 and v2 exist side by side to be compared, so they must differ.

    The failure this catches is copying a folder to make a variant and forgetting
    to change the weights: two rows on the leaderboard, one policy, and a
    difference in their scores that is pure noise being read as progress.
    """
    import json

    v1, v2 = (json.loads(pathlib.Path(f"bots/sarsa-{v}/artifacts/weights.json")
                         .read_text(encoding="utf-8")) for v in ("v1", "v2"))
    assert v1["encoding_version"] != v2["encoding_version"]
    assert len(v1["weights"]) != len(v2["weights"])


def test_every_llm_bot_uses_the_shared_harness_and_differs_from_the_others(monkeypatch):
    """Same loop, and no two bots identical in every dimension.

    A benchmark of models compares models only if the harness is held still, so
    an LLM bot that reimplements the loop is measuring something else. Sharing a
    PROMPT is fine and sometimes the point: `llm-raw` is `llm-survivor` word for
    word with a different state view, which is what makes the pair a single
    variable. What must not repeat is the whole configuration — two bots alike
    in prompt, view and tools are one bot under two names, and the difference
    between their rows would be pure noise read as a finding.
    """
    from pokelike.bot.catalogue import BOTS, available as on_disk, load_class
    from pokelike.bot.llm import HARNESS, LLMBot

    for var, val in (("FW_ENDPOINT", "https://x.invalid"),
                     ("FW_TOKEN", "t"), ("MODEL_ID", "m")):
        monkeypatch.setenv(var, val)

    seen = {}
    for name in [n for n in on_disk() if n.startswith("llm-")]:
        cls = load_class(BOTS / name / "bot.py")
        assert issubclass(cls, LLMBot), f"{name} does not build on the shared harness"
        assert cls.harness_version == HARNESS, f"{name} pins an old harness version"
        assert cls.config.prompt, f"{name} has no prompt"
        bot = cls()
        shape = (cls.config.prompt, bot._state_view_label(), tuple(bot.tool_names()), cls.config.model)
        assert shape not in seen, f"{name} is identical to {seen.get(shape)}"
        seen[shape] = name
    assert len(seen) >= 2, "there is nothing to compare"


def test_an_llm_bot_refuses_to_build_without_credentials(monkeypatch):
    """Never a silent default: a bot that cannot reach a model must say so.

    Falling back here would play a whole run on the backup heuristic and file it
    as an LLM result — a leaderboard row no model ever played.
    """
    from pokelike.bot.llm import LLMBot, LLMConfig, LLMConfigError

    class Probe(LLMBot):
        config = LLMConfig(prompt="x")

    for var in ("FW_ENDPOINT", "FW_TOKEN", "MODEL_ID"):
        monkeypatch.delenv(var, raising=False)
    with pytest.raises(LLMConfigError) as e:
        Probe()
    assert "FW_ENDPOINT" in str(e.value)

    monkeypatch.setenv("FW_ENDPOINT", "https://example.invalid")
    monkeypatch.setenv("FW_TOKEN", "t")
    with pytest.raises(LLMConfigError) as e:
        Probe()
    assert "MODEL_ID" in str(e.value)


def test_a_bot_may_add_its_own_tools_but_not_remove_play(monkeypatch):
    """Tools are overridable, because a prompt is not the only thing worth trying.

    `play` is the exception, checked once at construction rather than discovered
    fifty runs in: it is how a turn ends, so without it every turn exhausts its
    rounds and falls back — a whole benchmark of our backup heuristic, filed
    under the model's name, with nothing that looks wrong until you read
    `fallback_rate`.
    """
    from pokelike.bot.llm import LLMBot, LLMConfig, LLMConfigError

    for var, val in (("FW_ENDPOINT", "https://x.invalid"),
                     ("FW_TOKEN", "t"), ("MODEL_ID", "m")):
        monkeypatch.setenv(var, val)

    class Extra(LLMBot):
        config = LLMConfig(prompt="x", extra_tools=[
            {"type": "function", "function": {"name": "bag", "parameters": {}}}])

        def answer_tool(self, name, args, state):
            return "a potion" if name == "bag" else super().answer_tool(name, args, state)

    bot = Extra()
    assert "bag" in bot.tool_names() and "play" in bot.tool_names()
    assert bot.answer_tool("bag", {}, {}) == "a potion"
    assert "empty team" in bot.answer_tool("team_details", {}, {"team": []})
    # An invented tool is answered, not raised: the model should be told and
    # allowed to carry on, not have the turn thrown away and played by fallback.
    assert "unknown tool" in bot.answer_tool("invented", {}, {})
    # And the difference is recorded, so the row is not read as comparable.
    assert bot.metadata()["stock_tools"] is False

    class NoPlay(LLMBot):
        config = LLMConfig(prompt="x")

        def tools(self):
            return []

    with pytest.raises(LLMConfigError) as e:
        NoPlay()
    assert "play" in str(e.value)


def test_the_state_view_is_the_bots_to_choose_and_cannot_break_the_plumbing(monkeypatch):
    """What the model reads each turn is a knob, and replacing it is safe.

    The old hook mixed the view with the journal and the "pick an index" line,
    so a bot that replaced it wholesale silently lost its memory and stopped
    telling the model how many options there were — and kept running, just
    worse, for reasons nothing reported.
    """
    from pokelike.bot.llm import LLMBot, LLMConfig, LLMConfigError

    for var, val in (("FW_ENDPOINT", "https://x.invalid"),
                     ("FW_TOKEN", "t"), ("MODEL_ID", "m")):
        monkeypatch.setenv(var, val)

    state = {"screen": "map-screen", "steps": 3, "team": [], "bag": ["Potion"],
             "actions": [{"kind": "node", "id": "n1_0", "node": "catch"},
                         {"kind": "node", "id": "n1_1", "node": "battle"}]}

    class Probe(LLMBot):
        config = LLMConfig(prompt="x")

    seen = {spec: Probe(view=spec).render_state(state)
            for spec in ("screen", "json", "both")}
    assert "Potion" in seen["json"], "the raw dict must carry the whole state"
    assert len(seen["both"]) > len(seen["screen"]), "both is the view plus the dict"
    assert Probe(view=["bag"]).render_state(state) == '{"bag":["Potion"]}'
    # A key absent on this screen is skipped, not an error: `map` is gone during
    # a battle, and a view that raises there would end the run.
    assert Probe(view=["bag", "map"]).render_state(state) == '{"bag":["Potion"]}'

    assert Probe(view="json")._state_view_label() == "json"
    assert Probe(view=["bag"])._state_view_label() == "keys:bag"
    # A nonsense view is now rejected the moment the bot is built, by the config,
    # rather than turns later inside render_state.
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        Probe(view="nonsense")

    class Custom(LLMBot):
        config = LLMConfig(prompt="x")

        def render_state(self, state):
            return "ONLY MINE"

    bot = Custom()
    bot.journal = ["step 1: [0] went to the trainer"]
    whole = bot._build_user_message(state)
    assert "ONLY MINE" in whole
    assert "step 1: [0] went to the trainer" in whole, \
        "replacing the view cost the bot its memory"
    assert "Pick an index between 0 and 1" in whole, "the model was not told the range"
    assert bot._state_view_label() == "custom", "a custom view must be recorded as one"


def test_the_journal_records_the_action_not_the_models_sentence(monkeypatch):
    """The model's own guess must not come back to it as a record of events.

    It used to record `why` alone under a heading reading YOUR RECENT MOVES, so a
    plan ("a second Pokemon matters more than one more fight this early") read as
    a thing that had happened, one turn later, with nothing to tell the two apart.
    """
    from pokelike.bot.llm import LLMBot, LLMConfig

    for var, val in (("FW_ENDPOINT", "https://x.invalid"),
                     ("FW_TOKEN", "t"), ("MODEL_ID", "m")):
        monkeypatch.setenv(var, val)

    class B(LLMBot):
        config = LLMConfig(prompt="x")

    bot = B()
    state = {"steps": 7, "actions": [
        {"kind": "node", "id": "n2_1", "node": "trainer"},
        {"kind": "element", "label": "Take Potion"},
    ]}
    bot._cache_decision(state, 0, "a second Pokemon matters more than one more fight")

    entry = bot.journal[-1]
    assert "node n2_1 (trainer)" in entry, "what was done is not in the record"
    assert "it said:" in entry, "the reasoning is worth keeping, just not as fact"
    assert entry.index("node n2_1") < entry.index("it said:"), \
        "the game's record comes first, the talk about it second"

    bot._cache_decision({**state, "steps": 8}, 1, "")
    assert "Take Potion" in bot.journal[-1], "a non-node action needs its label"
    assert "(nothing)" in bot.journal[-1], "silence must not look like a missing turn"


def test_the_journal_heading_says_which_half_is_evidence(monkeypatch):
    """Separating them in the data is only half of it: the model has to be told."""
    from pokelike.bot.llm import LLMBot, LLMConfig

    for var, val in (("FW_ENDPOINT", "https://x.invalid"),
                     ("FW_TOKEN", "t"), ("MODEL_ID", "m")):
        monkeypatch.setenv(var, val)

    class B(LLMBot):
        config = LLMConfig(prompt="x")

        def render_state(self, state):
            return "V"

    bot = B()
    bot._cache_decision({"steps": 1, "actions": [{"kind": "node", "id": "n0", "node": "catch"}]},
                0, "worth a try")
    whole = bot._build_user_message({"steps": 2, "actions": [{"kind": "node", "id": "n1",
                                                     "node": "battle"}]})
    assert "YOUR RECENT MOVES" not in whole, "the old heading claimed too much"
    assert "not something that has been verified" in whole


def test_a_name_matching_two_bots_is_an_error_not_a_guess():
    """`--bot sarsa` with sarsa-v1 and sarsa-v2 on disk must refuse to choose.

    Variants of one idea share a name, so picking one silently produces a result
    that looks entirely plausible and is about the wrong bot.
    """
    from pokelike.bot import resolve

    assert resolve("sarsa-v1") == "sarsa-v1"
    assert resolve("rand") == "random", "a unique prefix should still work"
    with pytest.raises(KeyError) as e:
        resolve("sarsa")
    assert "sarsa-v1" in e.value.args[0] and "sarsa-v2" in e.value.args[0]


def test_unknown_bot_gives_a_useful_error():
    with pytest.raises(KeyError) as e:
        create("nonexistent")
    assert "random" in e.value.args[0]


def test_random_bot_is_reproducible():
    state = {"actions": [{}] * 5, "steps": 0}
    a = create("random", seed=7)
    b = create("random", seed=7)
    a.reset(7)
    b.reset(7)
    assert [a.act(state) for _ in range(20)] == [b.act(state) for _ in range(20)]


def test_random_bot_stays_in_range():
    state = {"actions": [{}] * 3, "steps": 0}
    b = create("random", seed=1)
    b.reset(1)
    assert all(0 <= b.act(state) < 3 for _ in range(50))


def test_abstract_bot_cannot_be_instantiated():
    with pytest.raises(TypeError):
        Bot()


# --------------------------------------------------------------- render


SAMPLE_STATE = {
    "screen": "map-screen",
    "steps": 4,
    "run": {"map": 0, "badges": 1},
    "team": [
        {"name": "Bulbasaur", "level": 5, "hp": 19, "max_hp": 19,
         "types": ["Grass", "Poison"], "item": None, "shiny": True},
        {"name": "Charmander", "level": 7, "hp": 0, "max_hp": 22,
         "types": ["Fire"], "item": "Life Orb", "shiny": False},
    ],
    "bag": ["Potion"],
    "map": {
        "nodes": [
            {"id": "n0_0", "kind": "start", "layer": 0, "col": 0,
             "accessible": False, "visited": True, "revealed": True},
            {"id": "n1_0", "kind": "catch", "layer": 1, "col": 0,
             "accessible": True, "visited": False, "revealed": True},
            {"id": "n1_1", "kind": "battle", "layer": 1, "col": 1,
             "accessible": True, "visited": False, "revealed": True},
            {"id": "n9_9", "kind": "boss", "layer": 9, "col": 0,
             "accessible": False, "visited": False, "revealed": False},
        ],
        "edges": [["n0_0", "n1_0"], ["n0_0", "n1_1"]],
        "current": "n0_0",
    },
    "actions": [
        {"kind": "node", "id": "n1_0", "node": "catch", "layer": 1, "col": 0},
        {"kind": "node", "id": "n1_1", "node": "battle", "layer": 1, "col": 1},
    ],
    "done": False,
}


def test_map_marks_position_and_legal_moves():
    text = render.map_view(SAMPLE_STATE["map"])
    assert "[@]" in text, "the current position is not marked"
    assert "<o>" in text and "<x>" in text, "legal moves are not marked"
    assert "B" not in text, "an unrevealed node must not show up"


TUTOR_OFFER = {"0": {"name": "Energy Ball", "power": 90, "type": "Grass",
                     "special": True}}


def test_the_tutor_block_appears_only_on_the_tutor_screen():
    """It used to appear on EVERY turn, which is 187 characters of prompt a turn.

    The bridge asks the engine what the tutor would offer each team member on
    every state, so `offered_moves` is always there; `tutor_view` renders
    whenever it is, and nothing was gating on the screen. Measured on seed 10000:
    the block was on 11 of the first 13 turns, not one of them a tutor.
    """
    off_tutor = {**SAMPLE_STATE, "offered_moves": TUTOR_OFFER}
    assert "MOVE TUTOR" not in render.screen(off_tutor)

    on_tutor = {**off_tutor, "screen": "move-tutor-screen"}
    text = render.screen(on_tutor)
    assert "MOVE TUTOR" in text
    assert "Energy Ball" in text, "the offer itself must still be readable"


def test_tutor_view_still_answers_when_asked_off_the_tutor_screen():
    """The gate is the caller's, not the function's.

    A bot planning several maps ahead has a reason to ask what the tutor would
    offer before reaching one, and no way to get it back if this refused.
    """
    text = render.tutor_view({**SAMPLE_STATE, "offered_moves": TUTOR_OFFER})
    assert "Energy Ball" in text


def test_team_shows_hp_and_shiny():
    text = render.team_view(SAMPLE_STATE["team"])
    assert "Bulbasaur" in text and "19/19" in text
    assert "Life Orb" in text
    assert "*" in text, "the shiny is not marked"


def test_actions_are_numbered_from_zero():
    text = render.actions_view(SAMPLE_STATE["actions"])
    assert "[0]" in text and "[1]" in text


def test_screen_survives_an_empty_state():
    """A caller should never get an exception just for rendering early state."""
    assert render.screen({"actions": []})


def test_screen_contains_the_pieces():
    text = render.screen(SAMPLE_STATE)
    for piece in ("Bulbasaur", "n1_0", "[@]"):
        assert piece in text


# ----------------------------------------------------------------- stats


FINAL_STATE = {"screen": "gameover-screen", "run": {"badges": 2}, "team": []}
ALIVE_STATE = {"run": {"badges": 2}, "team": [{"name": "Pikachu", "level": 12,
                                               "hp": 3, "max_hp": 30}]}
SCORE = {
    "points": 1005,
    "points_no_time": 25,
    "breakdown": {"enemiesKO": 9, "faints": 4, "mapsCleared": 1,
                  "winBonus": 0, "legendaries": 0, "shinies": 0, "timeBonus": 980},
    "stats": {"catches": 3, "totalDamageDealt": 220, "highestLevel": 12},
}


def test_record_then_read_back(temp_db):
    idx = record(bot="probe", seed=1, state=FINAL_STATE, score=SCORE,
                 steps=17, alive=ALIVE_STATE, path=temp_db)
    assert idx > 0
    rows = recent(5, path=temp_db)
    assert len(rows) == 1
    assert rows[0]["bot"] == "probe"
    assert rows[0]["points"] == 25, "it must store the score without the time bonus"


def test_the_team_comes_from_the_alive_state(temp_db):
    """The regression that started this: at game over the final state is empty."""
    import json
    import sqlite3

    record(bot="probe", seed=1, state=FINAL_STATE, score=SCORE,
           steps=17, alive=ALIVE_STATE, path=temp_db)

    conn = sqlite3.connect(temp_db)
    (team,) = conn.execute("SELECT team FROM runs").fetchone()
    assert json.loads(team)[0]["name"] == "Pikachu"


def test_summary_aggregates_per_bot(temp_db):
    for seed in (1, 2, 3):
        record(bot="alpha", seed=seed, state=FINAL_STATE, score=SCORE,
               steps=10, alive=ALIVE_STATE, path=temp_db)
    record(bot="beta", seed=1, state=FINAL_STATE, score=SCORE,
           steps=10, alive=ALIVE_STATE, path=temp_db)

    rows = {r["bot"]: r for r in summary(path=temp_db)}
    assert rows["alpha"]["runs"] == 3
    assert rows["beta"]["runs"] == 1
    assert rows["alpha"]["badges_best"] == 2
    assert rows["alpha"]["score_avg"] == 25


def test_empty_summary_does_not_blow_up(temp_db):
    assert "no runs" in format_summary(summary(path=temp_db))


def test_explain_describes_the_columns(temp_db):
    record(bot="alpha", seed=1, state=FINAL_STATE, score=SCORE,
           steps=10, alive=ALIVE_STATE, path=temp_db)
    rows = summary(path=temp_db)
    short = format_summary(rows)
    long = format_summary(rows, explain=True)
    assert len(long) > len(short)



def test_a_bot_may_carry_its_own_bridge(tmp_path, monkeypatch):
    """The state is written by hand, so adding to it needs a file, not a hook.

    `view()`, `EXTRA_TOOLS` and `run_tool()` cover almost everything a bot wants,
    but none of them can invent data the bridge never read out of the engine. A bot
    that needs a field nobody thought to expose puts its own `bridge.js` in
    `artifacts/`, and `artifacts/` specifically, because the leaderboard hashes
    everything under it: the score stays checkable without a line of new code.
    """
    import pokelike.interfaces.cli.main as cli
    from pokelike.bot import catalogue

    root = tmp_path / "bots"
    (root / "mine" / "artifacts").mkdir(parents=True)
    (root / "mine" / "bot.py").write_text(
        "from pokelike.bot.base import Bot\n"
        "class MyBot(Bot):\n"
        "    name = 'mine'\n"
        "    def act(self, state): return 0\n"
    )
    monkeypatch.setattr(catalogue, "BOTS", root)

    assert cli._own_bridge("mine") is None, "no file, no override"

    own = root / "mine" / "artifacts" / "bridge.js"
    own.write_text("// mine\n")
    assert cli._own_bridge("mine") == own
    assert cli._own_bridge("min") == own, "a unique prefix resolves like everywhere else"

    # A path is how a bot inside an experiment folder is played without moving it.
    assert cli._own_bridge(str(root / "mine")) == own

    assert cli._own_bridge(None) is None
    assert cli._own_bridge("no-such-bot") is None, "must not raise: the bot is already built"


def test_a_bots_own_bridge_lands_in_its_fingerprint(tmp_path):
    """Which is the whole reason it goes in artifacts/ rather than beside bot.py."""
    from pokelike.arena.leaderboard import fingerprint

    d = tmp_path / "mine"
    (d / "artifacts").mkdir(parents=True)
    (d / "bot.py").write_text("x = 1\n")

    before = fingerprint(d)
    (d / "artifacts" / "bridge.js").write_text("// mine\n")
    after = fingerprint(d)
    assert before != after, "a custom bridge must not be invisible to the record"

    # Beside bot.py it would NOT be hashed, which is why the convention matters.
    (d / "artifacts" / "bridge.js").unlink()
    (d / "bridge.js").write_text("// mine\n")
    assert fingerprint(d) == before
