"""Fast tests that need no browser, no network, and no game copy."""

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
    nothing checks the folder until something tries to play it. This test is that
    check. A folder that will not load is a bot nobody can run, including its author.

    The test stops at the class on purpose. Building one is allowed to need things a
    test does not have; the LLM bot refuses to construct without credentials, which
    is deliberate and right.
    """
    from pokelike.bot.catalogue import BOTS, available as on_disk, load_class

    names = on_disk()
    assert names, "bots/ has no bots in it"
    for name in names:
        cls = load_class(BOTS / name / "bot.py")
        assert issubclass(cls, Bot), f"{name} does not inherit from Bot"


def test_the_baseline_is_always_available():
    """The `random` bot must build with no bots/ folder at all, since `compare()` defaults to it."""
    assert "random" in available()
    assert isinstance(create("random", seed=1), Bot)


def test_the_sarsa_bot_freezes_exactly_the_features_it_was_trained_on():
    """The copy in `bots/sarsa-v2/bot.py` must stay identical to the training code.

    Weights are a plain list of numbers where index 43 only means `mon_new_type`
    because `feature_names()` says so. Inserting one feature on the training side
    makes every index after it silently point somewhere else, so the same file of
    weights becomes a different policy, including policies already on the standings.

    If this fails, the fix is to bump `FEATURES_VERSION` and retrain, never to
    quietly paste the new names across.
    """
    from experiments.sarsa.features import feature_names as trained_on

    from pokelike.bot.catalogue import load_class

    frozen = load_class(pathlib.Path("bots/sarsa-v2/bot.py")).__module__
    import sys

    assert sys.modules[frozen].feature_names() == trained_on()


# Every branch of `features()`, as states rather than as names, including a map node with
# its crosses and its lookahead, both Pokemon cards, the item screen, the two
# screens that list the team and mean opposite things, and a tutor offer. Built
# by hand because this has to stay a fast test, with no browser and no game copy.
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
    # A team of one and nothing decided yet, so every `or []` fallback fires at once.
    out.append({"screen": "map-screen", "run": {}, "team": [],
                "actions": base["actions"], "map": board("n0_0"),
                "can_reorder": False})
    return out


@pytest.mark.parametrize("frozen_bot", ["bots/sarsa-v2/bot.py",
                                        "experiments/drrn/bot.py"])
def test_a_frozen_feature_copy_computes_the_same_vector(frozen_bot):
    """The copies must agree on the numbers, not only on the names.

    The test above compares `feature_names()`, which catches an inserted or
    reordered feature and misses a changed one. Rescaling `mon_power` by 100 on one
    side means both lists still match while every weight that reads the feature means
    something else.

    This matters most for `experiments/drrn/`, where the two halves of one
    experiment sit on opposite sides of the copy. `collect.py` and `train.py`
    import the training features, while `bot.py` carries the frozen ones, so a drift
    fits one feature map and benchmarks another. Both sides keep 100 features and
    nothing raises; the only symptom is a benchmark number that means nothing.
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
    """Both templates must load, because they break differently.

    The LLM one is full of JSON (tool schemas are literal braces) and the
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

    `artifacts()` and `record_result` only run after a complete benchmark, so
    nothing reached them for minutes at a time and three separate breakages sat
    there unseen. A relative import in a recovered bot, an artifact copied onto
    itself now that a bot's folder is its archive rather than being copied into
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
        # The call that was never made, because a bot may declare artifacts, and a
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
    """The `--bot <path>` flag loads the bot from any folder, typically an experiment's.

    The point is that measuring a candidate never requires moving it, and above
    all never requires wearing another bot's name. You benchmark the folder you
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
    same arithmetic is exactly the kind of split that drifts without saying so.
    The bot would keep playing, just a different policy from the one measured.

    Skipped where numpy is absent because numpy belongs to the experiments group,
    not to the package.
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
    to change the weights. Two rows on the standings, one policy, and a
    difference in their scores that is pure noise being read as progress.
    """
    import json

    v1, v2 = (json.loads(pathlib.Path(f"bots/sarsa-{v}/artifacts/weights.json")
                         .read_text(encoding="utf-8")) for v in ("v1", "v2"))
    assert v1["encoding_version"] != v2["encoding_version"]
    assert len(v1["weights"]) != len(v2["weights"])


def test_every_llm_bot_uses_the_shared_harness_and_differs_from_the_others(monkeypatch):
    """Every LLM bot shares the same loop, and no two bots are identical in every dimension.

    A benchmark of models compares models only if the harness is held still, so
    an LLM bot that reimplements the loop is measuring something else. Sharing a
    prompt is fine and sometimes the point. `llm-raw` is `llm-survivor` word for
    word with a different state view, which is what makes the pair a single
    variable. What must not repeat is the whole configuration; two bots alike
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
    """A silent default here must never happen.

    Falling back would play a whole run on the backup heuristic and file the result
    as an LLM result, producing a standings row no model ever played.
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

    The `play` tool is the exception, checked once at construction rather than
    discovered fifty runs in. The `play` tool is how a turn ends, so without it every
    turn exhausts its rounds and falls back. A whole benchmark of our backup
    heuristic, filed under the model's name, with nothing that looks wrong until you
    read `fallback_rate`.
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
    # An invented tool is answered rather than raised, because the model should be told and
    # allowed to carry on without having the turn thrown away and played by fallback.
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


def test_decorated_tool_deduplicates_with_bag_tool(monkeypatch):
    """A bot with bag_tool=True and its own @tool-decorated `bag` sends ONE bag.

    Precedence: decorated > extra_tools > shared. The most specific wins and
    providers reject a duplicated function name.
    """
    from pokelike.bot.llm import LLMBot, LLMConfig, tool

    for var, val in (("FW_ENDPOINT", "https://x.invalid"),
                     ("FW_TOKEN", "t"), ("MODEL_ID", "m")):
        monkeypatch.setenv(var, val)

    class DedupBot(LLMBot):
        config = LLMConfig(prompt="x", bag_tool=True)

        @tool("My own bag tool, more detailed.")
        def bag(self, state) -> str:
            return "decorated bag wins"

    bot = DedupBot()
    names = bot.tool_names()
    assert names.count("bag") == 1, f"expected one bag, got {names.count('bag')}"
    assert "play" in names, "play must still be present"
    # The decorated version wins over the shared one in dispatch.
    assert bot.answer_tool("bag", {}, {"bag": ["Potion"]}) == "decorated bag wins"

    # This also tests extra_tools collision, where the decorated version still wins.
    class DedupExtra(LLMBot):
        config = LLMConfig(prompt="x", extra_tools=[
            {"type": "function", "function": {
                "name": "bag", "description": "extra bag",
                "parameters": {"type": "object", "properties": {}}}}])

        @tool("Decorated bag, should win over extra_tools.")
        def bag(self, state) -> str:
            return "decorated wins over extra"

    bot2 = DedupExtra()
    assert bot2.tool_names().count("bag") == 1
    assert bot2.answer_tool("bag", {}, {}) == "decorated wins over extra"


def test_decorated_tool_errors_are_returned_not_raised(monkeypatch):
    """A @tool method that throws returns the error as a message to the model.

    In: a decorated tool that raises. Out: an error string, not an exception.
    """
    from pokelike.bot.llm import LLMBot, LLMConfig, tool

    for var, val in (("FW_ENDPOINT", "https://x.invalid"),
                     ("FW_TOKEN", "t"), ("MODEL_ID", "m")):
        monkeypatch.setenv(var, val)

    class BuggyBot(LLMBot):
        config = LLMConfig(prompt="x")

        @tool("Always fails.")
        def buggy(self, state) -> str:
            raise RuntimeError("kaboom")

    bot = BuggyBot()
    result = bot.answer_tool("buggy", {}, {})
    assert "error in buggy" in result
    assert "RuntimeError" in result
    assert "kaboom" in result


def test_decorated_tool_inheritance(monkeypatch):
    """A subclass of a bot with @tool methods inherits them and may override.

    In: a parent with a decorated tool, a child that overrides it. Out: the
    child's version wins.
    """
    from pokelike.bot.llm import LLMBot, LLMConfig, tool

    for var, val in (("FW_ENDPOINT", "https://x.invalid"),
                     ("FW_TOKEN", "t"), ("MODEL_ID", "m")):
        monkeypatch.setenv(var, val)

    class Parent(LLMBot):
        config = LLMConfig(prompt="x")

        @tool("Parent's info tool.")
        def info(self, state) -> str:
            return "parent info"

    class Child(Parent):
        @tool("Child's info tool, overridden.")
        def info(self, state) -> str:
            return "child info"

    parent = Parent()
    child = Child()
    assert parent.answer_tool("info", {}, {}) == "parent info"
    assert child.answer_tool("info", {}, {}) == "child info"
    assert parent.tool_names().count("info") == 1
    assert child.tool_names().count("info") == 1


def test_decorated_tool_metadata_reports_them(monkeypatch):
    """metadata() should report which decorated tools a bot declared."""
    from pokelike.bot.llm import LLMBot, LLMConfig, tool

    for var, val in (("FW_ENDPOINT", "https://x.invalid"),
                     ("FW_TOKEN", "t"), ("MODEL_ID", "m")):
        monkeypatch.setenv(var, val)

    class WithTools(LLMBot):
        config = LLMConfig(prompt="x")

        @tool("A custom tool.")
        def my_tool(self, state) -> str:
            return "hi"

    bot = WithTools()
    meta = bot.metadata()
    assert "decorated_tools" in meta
    assert "my_tool" in meta["decorated_tools"]


def test_the_state_view_is_the_bots_to_choose_and_cannot_break_the_plumbing(monkeypatch):
    """What the model reads each turn is a knob, and replacing the view is safe.

    The view must be separate from the journal and the "pick an index" line, so
    that a bot replacing render_state does not silently lose its memory or stop
    telling the model how many options there are.
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

    The journal records what the game did (the action), then what the model said
    about it (the reasoning). Separating these keeps plans ("a second Pokemon
    matters more than one more fight this early") from looking like a thing that
    had happened, one turn later, with nothing to tell the two apart.
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


def test_parse_index_takes_the_last_valid_number(monkeypatch):
    """A model reasons before it concludes, so the answer is the LAST index named."""
    from pokelike.bot.llm import LLMBot, LLMConfig
    for var, val in (("FW_ENDPOINT", "https://x.invalid"), ("FW_TOKEN", "t"),
                     ("MODEL_ID", "m")):
        monkeypatch.setenv(var, val)

    class B(LLMBot):
        config = LLMConfig(prompt="x")

    b = B()
    assert b._parse_index("0 looks weak, 1 is risky, so I take 2", 3) == 2
    assert b._parse_index("nothing in range like 9 here", 3) is None


def test_play_index_as_string_is_accepted(monkeypatch):
    """The value `{"index": "2"}` should be parsed as the integer 2, not treated as a
    malformed answer that falls back to the heuristic."""
    from pokelike.bot.llm import LLMBot, LLMConfig
    for var, val in (("FW_ENDPOINT", "https://x.invalid"), ("FW_TOKEN", "t"),
                     ("MODEL_ID", "m")):
        monkeypatch.setenv(var, val)

    class B(LLMBot):
        config = LLMConfig(prompt="x")

    b = B()
    assert b._as_index("2") == 2 and b._as_index(2) == 2 and b._as_index(" 3 ") == 3
    assert b._as_index("two") is None and b._as_index(True) is None and b._as_index(None) is None


def test_memory_minus_one_keeps_every_turn(monkeypatch):
    """memory=-1 is an unbounded, append-only journal, while a positive value caps it."""
    from pokelike.bot.llm import LLMBot, LLMConfig
    for var, val in (("FW_ENDPOINT", "https://x.invalid"), ("FW_TOKEN", "t"),
                     ("MODEL_ID", "m")):
        monkeypatch.setenv(var, val)

    class Keep(LLMBot):
        config = LLMConfig(prompt="x", memory=-1)

    class Cap(LLMBot):
        config = LLMConfig(prompt="x", memory=2)

    def st(k):
        return {"steps": k, "actions": [{"kind": "node", "id": f"n{k}", "node": "catch"}]}

    keep, cap = Keep(), Cap()
    for k in range(5):
        keep._cache_decision(st(k), 0, f"why{k}")
        cap._cache_decision(st(k), 0, f"why{k}")
    assert len(keep.journal) == 5, "memory=-1 keeps every turn"
    assert len(cap.journal) == 2, "memory=2 keeps only the last two"


def test_a_name_matching_two_bots_is_an_error_not_a_guess():
    """The `--bot sarsa` flag with sarsa-v1 and sarsa-v2 on disk must refuse to choose.

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
    """The tutor block used to appear on every turn, which is 187 characters of prompt per turn.

    The bridge asks the engine what the tutor would offer each team member on
    every state, so `offered_moves` is always present. The `tutor_view` function
    renders whenever the field is present, and nothing was gating on the screen.
    Measured on seed 10000, the block appeared on 11 of the first 13 turns, none
    of them a tutor.
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
    offer before reaching one, and no way to get the information back if this
    function refused.
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
    """This regression started because at game over the final state is empty."""
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
    """The state is written by hand, so adding to it needs a file, not just a hook.

    `view()`, `EXTRA_TOOLS` and `run_tool()` cover almost everything a bot wants,
    but none of them can invent data the bridge never read out of the engine. A bot
    that needs a field nobody thought to expose puts its own `bridge.js` in
    `artifacts/`. The `artifacts/` directory specifically, because the standings hash
    everything under it so the score stays checkable without new code.
    """
    import pokelike.interfaces.cli.shared as cli
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

    # Beside bot.py it would not be hashed, which is why the convention matters.
    (d / "artifacts" / "bridge.js").unlink()
    (d / "bridge.js").write_text("// mine\n")
    assert fingerprint(d) == before


# ---------------------------------------------------------------- .env as a source
#
# `.env` was already where credentials lived for the container (compose reads it
# through `env_file:`), but nothing on the host did, so every local run needed an
# export or `--api-key` on the command line. The command line is the one place a key
# must not be, because `ps` shows it to every other user of the machine and the
# shell saves it.


def _dotenv_at(root, body: str, monkeypatch):
    """Points the loader at a .env written under tmp_path, and clears the vars."""
    import pokelike.interfaces.cli.shared as sh

    (root / ".env").write_text(body, encoding="utf-8")
    # The loader finds the file from its own location, so the location is what the
    # test has to move.
    fake = root / "src" / "pokelike" / "interfaces" / "cli" / "shared.py"
    fake.parent.mkdir(parents=True, exist_ok=True)
    fake.touch()
    monkeypatch.setattr(sh, "__file__", str(fake))
    return sh


def test_env_file_fills_what_the_shell_did_not(tmp_path, monkeypatch):
    for name in ("FW_ENDPOINT", "FW_TOKEN", "MODEL_ID"):
        monkeypatch.delenv(name, raising=False)
    sh = _dotenv_at(tmp_path, "FW_ENDPOINT=https://e\nFW_TOKEN=abc\nMODEL_ID=a/b\n",
                    monkeypatch)
    assert sorted(sh.load_dotenv()) == ["FW_ENDPOINT", "FW_TOKEN", "MODEL_ID"]
    import os
    assert os.environ["FW_ENDPOINT"] == "https://e"
    assert os.environ["FW_TOKEN"] == "abc"


def test_the_shell_wins_over_the_file(tmp_path, monkeypatch):
    """A variable exported for one command must not be quietly replaced by a file.
    The reason it is `setdefault` and not assignment.
    """
    monkeypatch.setenv("FW_ENDPOINT", "https://exported")
    monkeypatch.delenv("FW_TOKEN", raising=False)
    sh = _dotenv_at(tmp_path, "FW_ENDPOINT=https://from-file\nFW_TOKEN=abc\n", monkeypatch)
    filled = sh.load_dotenv()
    import os
    assert os.environ["FW_ENDPOINT"] == "https://exported"
    assert "FW_ENDPOINT" not in filled, "it must report only what it actually set"
    assert os.environ["FW_TOKEN"] == "abc"


def test_the_file_may_be_written_the_way_people_write_shell(tmp_path, monkeypatch):
    """Comments, blank lines, `export`, and quotes around a value."""
    for name in ("A_ONE", "A_TWO", "A_THREE", "A_FOUR"):
        monkeypatch.delenv(name, raising=False)
    sh = _dotenv_at(tmp_path, "\n# a comment\n\nexport A_ONE=1\n"
                              'A_TWO="two words"\nA_THREE=\'quoted\'\n'
                              "not a pair\nA_FOUR=has=equals\n", monkeypatch)
    sh.load_dotenv()
    import os
    assert os.environ["A_ONE"] == "1"
    assert os.environ["A_TWO"] == "two words"
    assert os.environ["A_THREE"] == "quoted"
    assert os.environ["A_FOUR"] == "has=equals", "only the first = separates"


def test_no_env_file_is_not_an_error(tmp_path, monkeypatch):
    import pokelike.interfaces.cli.shared as sh

    fake = tmp_path / "src" / "pokelike" / "interfaces" / "cli" / "shared.py"
    fake.parent.mkdir(parents=True, exist_ok=True)
    fake.touch()
    monkeypatch.setattr(sh, "__file__", str(fake))
    assert sh.load_dotenv() == []


# ------------------------------------------------------- the conversations file
#
# What the model was actually given, recorded by wrapping the bot's own
# `call_model`. The approach is wrapping rather than a callback because the frozen
# harnesses build their own messages and cannot be edited (a recorded result hashes
# those files). So the recorder has to work from outside, and must leave the bot
# exactly as it found it.


def test_the_conversation_is_recorded_without_the_bot_cooperating(tmp_path):
    """A bot that knows nothing about logging still gets logged."""
    import json
    from pokelike.logging import Conversations

    class Frozen:                      # stands in for a frozen harness bot
        def call_model(self, messages):
            return {"content": "", "tool_calls": [{"function": {"name": "play"}}]}

    bot = Frozen()
    original = bot.call_model
    chat = Conversations(tmp_path / "c.jsonl")
    assert chat.watch(bot) is True
    chat.turn(10000, 0)
    bot.call_model([{"role": "system", "content": "rules"},
                    {"role": "user", "content": "screen"}])
    chat.flush()
    chat.turn(10000, 1)
    bot.call_model([{"role": "system", "content": "rules"},
                    {"role": "user", "content": "next screen"}])
    chat.close()

    rows = [json.loads(x) for x in (tmp_path / "c.jsonl").read_text().splitlines()]
    assert [r["step"] for r in rows] == [0, 1]
    assert [m["role"] for m in rows[0]["rounds"][0]["sent"]] == ["system", "user"]
    assert rows[1]["rounds"][0]["sent"][1]["content"] == "next screen"
    assert rows[0]["rounds"][0]["reply"]["tool_calls"], "the answer is kept too"
    # And the bot is as it was: the wrapper is gone.
    assert bot.call_model == original or bot.call_model.__func__ is original.__func__


def test_several_rounds_of_one_turn_are_one_line(tmp_path):
    """A turn that calls tools before playing is one conversation, not three."""
    import json
    from pokelike.logging import Conversations

    class Bot:
        def call_model(self, messages):
            return {"content": "ok"}

    bot = Bot()
    chat = Conversations(tmp_path / "c.jsonl")
    chat.watch(bot)
    chat.turn(10000, 5)
    convo = [{"role": "system", "content": "rules"}]
    for extra in ("first", "second", "third"):
        convo.append({"role": "user", "content": extra})
        bot.call_model(convo)          # the SAME list, appended to, as a loop does
    chat.close()

    rows = [json.loads(x) for x in (tmp_path / "c.jsonl").read_text().splitlines()]
    assert len(rows) == 1
    assert len(rows[0]["rounds"]) == 3
    # Each round must hold what was sent AT THE TIME, not the final state of the list.
    assert [len(r["sent"]) for r in rows[0]["rounds"]] == [2, 3, 4]


def test_a_bot_that_talks_to_no_model_writes_nothing(tmp_path):
    """The random bot, a policy, and a search have nothing to record and leave no empty file."""
    from pokelike.logging import Conversations

    class Policy:
        def act(self, state):
            return 0

    chat = Conversations(tmp_path / "c.jsonl")
    assert chat.watch(Policy()) is False
    chat.turn(10000, 0)
    chat.close()
    assert not (tmp_path / "c.jsonl").exists()


def test_the_scratchpad_keeps_the_words_and_drops_the_screen():
    """The last N turns travel verbatim, minus the screen they were looking at."""
    from pokelike.bot.llm import LLMBot

    obs = {"actions": [{"kind": "node", "id": "n1_0", "node": "catch"}],
           "team": [], "bag": [], "map": {"nodes": []}, "run": {"badges": 0},
           "screen": "map-screen", "seed": 1, "steps": 0}
    sent = []

    class Probe(LLMBot):
        def render_state(self, state):
            return "THE WHOLE SCREEN, which is long"      # stands in for the render
        def call_model(self, messages):
            sent.append([(m["role"], m.get("content") or "") for m in messages])
            return {"content": "", "tool_calls": [
                {"id": f"c{len(sent)}", "type": "function",
                 "function": {"name": "play", "arguments": '{"index":0,"why":"x"}'}}]}

    bot = Probe(seed=0, endpoint="http://x", token="t", model="m/m", scratch_turns=2)
    bot.reset(1)
    for step in range(3):
        bot.act({**obs, "steps": step})

    assert [r[0] for r in sent[0]] == ["system", "user"], "the first turn has no history"
    roles = [r[0] for r in sent[2]]
    assert roles.count("assistant") == 2, "two turns kept, cap respected"
    users = [c for role, c in sent[2] if role == "user"]
    # The kept screens are gone, replaced by one line each; the fresh one is whole.
    assert all("since changed" in u for u in users[:-1])
    assert "THE WHOLE SCREEN" in users[-1]
    # And it is per run, like the plan: notes are the only thing that crosses.
    bot.reset(2)
    assert [r[0] for r in [sent[-1]]][0] is not None
    sent.clear()
    bot.act({**obs, "steps": 0})
    assert [r[0] for r in sent[0]] == ["system", "user"], "reset emptied the scratchpad"


def test_what_a_kept_turn_shows_is_a_choice(monkeypatch):
    """Three modes for the user slot of a kept turn, with a seam behind them."""
    from pokelike.bot.llm import LLMBot

    obs = {"actions": [{"kind": "node", "id": "n1_0", "node": "catch"}],
           "team": [{"name": "Bulbasaur", "level": 5, "hp": 19, "max_hp": 19}],
           "bag": [], "map": {"nodes": []}, "run": {"badges": 0, "map": 0},
           "screen": "map-screen", "seed": 1, "steps": 3}

    def kept_slot(**cfg):
        sent = []

        class P(LLMBot):
            def render_state(self, state):
                return "THE FULL SCREEN"
            def call_model(self, messages):
                sent.append(messages)
                return {"content": "", "tool_calls": [
                    {"id": f"c{len(sent)}", "type": "function",
                     "function": {"name": "play", "arguments": '{"index":0,"why":"x"}'}}]}

        b = P(seed=0, endpoint="http://x", token="t", model="m/m", **cfg)
        b.reset(1)
        b.act(obs)
        b.act({**obs, "steps": 4})
        return [m["content"] for m in sent[-1] if m["role"] == "user"][0]

    assert "since changed" in kept_slot(scratch_turns=2)
    brief = kept_slot(scratch_turns=2, scratch_state="brief")
    assert "step 3" in brief and "Bulbasaur L5 19/19" in brief and len(brief) < 200
    assert kept_slot(scratch_turns=2, scratch_state="full") == "THE FULL SCREEN"


def test_scratch_turns_minus_one_keeps_every_turn():
    """-1 means keep-all, like memory=-1 for the journal."""
    from pokelike.bot.llm import LLMBot

    obs = {"actions": [{"kind": "node", "id": "n1_0", "node": "catch"}], "team": [],
           "bag": [], "map": {"nodes": []}, "run": {"badges": 0}, "screen": "map-screen",
           "seed": 1, "steps": 0}

    def held(turns, **cfg):
        sent = []

        class P(LLMBot):
            def render_state(self, state):
                return "screen"
            def call_model(self, messages):
                sent.append(messages)
                return {"content": "", "tool_calls": [
                    {"id": f"c{len(sent)}", "type": "function",
                     "function": {"name": "play", "arguments": '{"index":0,"why":"x"}'}}]}

        b = P(seed=0, endpoint="http://x", token="t", model="m/m", **cfg)
        b.reset(1)
        for step in range(turns):
            b.act({**obs, "steps": step})
        # the assistant messages of the last request, minus the current turn's own
        return sum(1 for m in sent[-1] if m["role"] == "assistant") - 1

    assert held(5, scratch_turns=-1) == 4, "every earlier turn kept"
    assert held(5, scratch_turns=2) == 2, "capped at two"
    assert held(5, scratch_turns=0) == 0, "off"


# ------------------------------------------------- the four things a bot does to tools
#
# Add, override, remove, and never touch `play`. Each is one line for the bot author,
# and the last one is a refusal rather than a knob.


def test_a_tool_is_added_overridden_and_removed_in_one_line_each():
    """In: bots declaring each way. Out: the tool list each asked for."""
    from pokelike.bot.llm import LLMBot, LLMConfig, tool

    def names(cls):
        return [t["function"]["name"]
                for t in cls(seed=0, endpoint="x", token="t", model="m").tools()]

    class Added(LLMBot):
        @tool("what you carry")
        def bag(self, state) -> str:
            return "ok"

    class Overridden(LLMBot):
        @tool("MY team view")
        def team_details(self, state) -> str:
            return "mine"

    class Removed(LLMBot):
        config = LLMConfig(prompt="p", drop_tools=("what_lies_ahead",))

    assert "bag" in names(Added)
    # Overriding is the same gesture as adding, with one schema that belongs to the bot.
    assert names(Overridden).count("team_details") == 1
    b = Overridden(seed=0, endpoint="x", token="t", model="m")
    assert b.answer_tool("team_details", {}, {}) == "mine"
    assert next(t for t in b.tools()
                if t["function"]["name"] == "team_details")["function"]["description"] \
        == "MY team view"
    assert "what_lies_ahead" not in names(Removed)


def test_play_may_be_neither_dropped_nor_redeclared():
    """The turn ends on `play`, so its schema is not a bot's to change.

    In: a bot trying each. Out: refused, with a reason, at build time.
    """
    import pytest

    from pokelike.bot.llm import LLMBot, LLMConfig, LLMConfigError, tool

    with pytest.raises(Exception):
        LLMConfig(prompt="p", drop_tools=("play",))

    class Redeclares(LLMBot):
        @tool("mine")
        def play(self, state, index: int) -> str:
            return "x"

    # Without this the loop would still end the turn on the tool name while reading
    # `index` and `why` out of a schema that no longer promises them.
    with pytest.raises(LLMConfigError):
        Redeclares(seed=0, endpoint="x", token="t", model="m").tools()


def test_exits_of_reads_the_map_edges():
    """The function shows where each option leads, which is why looking before choosing
    is possible."""
    from pokelike.core import render

    state = {
        "map": {"nodes": [{"id": "a", "kind": "trade"}, {"id": "b", "kind": "trainer"},
                          {"id": "p", "kind": "pokecenter"}, {"id": "q", "kind": "question"},
                          {"id": "r", "kind": "pokecenter"}],
                "edges": [("a", "p"), ("b", "p"), ("b", "q"), ("b", "r")]},
        "actions": [{"kind": "node", "id": "a", "node": "trade"},
                    {"kind": "node", "id": "b", "node": "trainer"},
                    {"kind": "button", "label": "BACK"}],
    }
    exits = render.exits_of(state)
    assert exits[0] == ["pokecenter"]
    # Faithful to the edges by default: two pokecenters are two pokecenters, which is
    # what `what_lies_ahead` has always said and models have been reading.
    assert exits[1] == ["pokecenter", "pokecenter", "question"]
    assert render.exits_of(state, unique=True)[1] == ["pokecenter", "question"]
    assert 2 not in exits, "a button is not a step on the map"
    assert render.exits_of({"actions": []}) == {}, "no map, no exits"


# ----------------------------------------------------------------- regions
#
# A region is a whole GAME: the engine keeps nothing across one, a new starter is
# picked and the badge count restarts. So a campaign is a sequence of runs, and the
# only thing that crosses is the BOT.


def test_a_region_is_named_or_numbered_and_nothing_else():
    """A region can be named or numbered; anything else is refused."""
    import pytest

    from pokelike.core.browser import REGIONS, normalise_region, region_name

    assert REGIONS == ("kanto", "johto", "hoenn", "sinnoh")
    assert normalise_region("JOHTO") == 2 and normalise_region(4) == 4
    assert region_name(3) == "hoenn"
    # Refused, not defaulted to Kanto: a typo would otherwise file a row for a
    # region that never played.
    for bad in (0, 5, "kalos", True):
        with pytest.raises(ValueError):
            normalise_region(bad)


def test_what_survives_a_region_boundary_is_a_setting():
    """Only the items listed in `keep_across_regions` survive a boundary."""
    from pokelike.bot.llm import LLMBot

    def loaded(**cfg):
        b = LLMBot(seed=0, endpoint="x", token="t", model="m",
                   notes_cap=4, plan_chars=100, scratch_turns=2, **cfg)
        b.reset(1)
        b.answer_tool("remember", {"note": "Brock is Rock"}, {})
        b.answer_tool("plan", {"route": "n1_0 then the trainer"}, {})
        b.journal = ["step 1: [0] catch"]
        b._scratch = [[{"role": "user", "content": "x"}]]
        return b

    b = loaded()                        # the default keeps the notes and nothing else
    b.reset_memory()
    assert b._notebook.notes == ["Brock is Rock"]
    assert b.plan == "" and b.journal == [] and b._scratch == []

    b = loaded(keep_across_regions=("notes", "journal", "scratchpad", "plan"))
    b.reset_memory()
    assert b._notebook.notes and b.plan and b.journal and b._scratch, "all of it kept"

    b = loaded(keep_across_regions=())
    b.reset_memory()
    assert not b._notebook.notes, "and the notes can go too"


def test_the_boundary_is_crossed_with_the_memory_still_intact():
    """The reason `region_cleared` exists is that a bot can summarise while the
    memory is still intact."""
    from pokelike.core import runner
    from pokelike.bot.llm import LLMBot

    seen = []

    class Bot(LLMBot):
        def region_cleared(self, done):
            # If the runner forgot first, this would be empty, which is the bug this
            # test exists to prevent.
            seen.append(self.memory_text())
            return f"{done['region']} -> {done['next']}"

    bot = Bot(seed=0, endpoint="x", token="t", model="m", notes_cap=4)
    bot.reset(1)
    bot.answer_tool("remember", {"note": "a Water lead walks Brock"}, {})
    bot.journal = ["step 1: [0] catch"]

    real = runner.play_run
    try:
        runner.play_run = lambda game, b, seed, region=1, **kw: {
            "seed": seed, "region": region if isinstance(region, str) else "kanto",
            "steps": 80, "badges": 8, "ending": "win-screen", "team": [], "trace": []}
        out = runner.play_campaign(None, bot, seed=1)
    finally:
        runner.play_run = real

    assert out["regions_played"] == 4 and out["regions_cleared"] == 4
    assert out["badges"] == 32, "eight per region, and they add up"
    assert len(seen) == 3, "three boundaries between four regions"
    assert "WHAT YOU DID" in seen[0], "the journal was still there when it was asked"
    assert bot._notebook.notes, "and the notes crossed every one of them"


def test_a_campaign_stops_at_the_first_region_not_won():
    """Carrying on after a loss would measure four regions and call it progress."""
    from pokelike.core import runner
    from pokelike.bot import RandomBot

    real = runner.play_run
    try:
        runner.play_run = lambda game, b, seed, region=1, **kw: {
            "seed": seed, "region": "kanto", "steps": 20, "badges": 1,
            "ending": "gameover-screen", "team": [], "trace": []}
        out = runner.play_campaign(None, RandomBot(seed=0), seed=1)
    finally:
        runner.play_run = real
    assert out["regions_played"] == 1 and out["regions_cleared"] == 0


def test_the_next_region_opens_with_what_the_last_one_left():
    """The opening text appears in the first prompt of a new region, then makes way."""
    from pokelike.bot.llm import LLMBot

    obs = {"actions": [{"kind": "node", "id": "n1_0", "node": "catch"}], "team": [],
           "bag": [], "map": {"nodes": [], "edges": []}, "run": {"badges": 0},
           "screen": "map-screen", "seed": 1, "steps": 0, "region": "johto"}
    b = LLMBot(seed=0, endpoint="x", token="t", model="m")
    b.reset(1)
    b.region_opening("Water leads carried the first three gyms.")
    assert "LAST REGION: Water leads" in b._build_user_message(obs)
    # It is context for the first decisions, not for all of them.
    b.journal = ["step 1: [0] catch"]
    assert "LAST REGION" not in b._build_user_message(obs)


def test_campaign_trace_says_which_region_each_decision_came_from():
    """The flattened trace is four regions long, so an entry with no region cannot be read."""
    from pokelike.core import runner
    from pokelike.bot import RandomBot

    real = runner.play_run
    try:
        runner.play_run = lambda game, b, seed, region=1, **kw: {
            "seed": seed, "region": ("kanto" if region in (1, "kanto") else "johto"),
            "steps": 2, "badges": 8, "ending": "win-screen", "team": [],
            "trace": [{"step": 0, "choice": 0}, {"step": 1, "choice": 1}]}
        out = runner.play_campaign(None, RandomBot(seed=0), seed=1,
                                   regions=["kanto", "johto"])
    finally:
        runner.play_run = real

    assert [e["region"] for e in out["trace"]] == ["kanto", "kanto", "johto", "johto"]
    # The per-region traces stay exactly as play_run wrote them, which is what keeps a
    # single-region decision log what it has always been.
    assert all("region" not in e for r in out["regions"] for e in r["trace"])


def test_a_campaign_answers_every_column_a_run_answers():
    """A blank in a table is a key nobody carried over. These keys cannot be typed by hand."""
    from pokelike.core import runner
    from pokelike.bot import RandomBot

    row = {"seed": 1, "region": "kanto", "steps": 20, "score": 15, "score_raw": 900,
           "badges": 8, "maps": 0, "kos": 30, "faints": 2, "ending": "win-screen",
           "stalled": False, "team": [], "final_state": {}, "score_detail": {},
           "trace": [{"step": 0}]}
    real = runner.play_run
    try:
        runner.play_run = lambda game, b, seed, region=1, **kw: dict(
            row, region=("kanto" if region in (1, "kanto") else "johto"))
        out = runner.play_campaign(None, RandomBot(seed=0), seed=1,
                                   regions=["kanto", "johto"])
    finally:
        runner.play_run = real

    assert not set(row) - set(out)
    # The measured columns are summed, the way badges are.
    assert (out["badges"], out["score"], out["kos"], out["faints"]) == (16, 30, 60, 4)
    # What says where it ended is inherited from the last region played.
    assert out["region"] == "johto"
