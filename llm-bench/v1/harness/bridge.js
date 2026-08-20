// Bridge between the game engine and Python.
//
// Injected into the page AFTER the game bundle has booted. It exposes a handful
// of functions on `window`, and that is the entire surface Python uses:
//
//   __pk_layer()    which screen or modal is active right now
//   __pk_choices()  the legal actions, as a stable ordered list
//   __pk_apply(c)   perform one of them
//   __pk_obs()      the full state, as plain JSON
//
// Worth stressing: no pixels are involved. `state` is a JavaScript object in
// memory and the buttons are DOM objects, both of which exist perfectly well
// without a window ever being drawn.
(() => {
  // The engine's names are globals declared with `let`/`function`: they live in
  // the script's global scope, not on `window`, so they need eval to read.
  const g = (n) => { try { return eval(n); } catch (e) { return undefined; } };

  const CFG = window.__PK_CFG;

  const shown = (e) => {
    if (!e) return false;
    const cs = getComputedStyle(e);
    if (cs.display === 'none' || cs.visibility === 'hidden' || cs.opacity === '0') return false;
    const r = e.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };

  // Where each screen keeps its choices; falls back to the screen itself.
  const CONTAINERS = {
    'starter-screen': '#starter-choices',
    'trainer-screen': '#trainer-choices',
    'catch-screen': '#catch-choices',
    'item-screen': '#item-choices',
    'passive-screen': '#passive-choices',
    'swap-screen': '#swap-choices',
    // The branching-evolution overlay keeps its options in their own container,
    // same as the screens do.
    'eevee-choice-overlay': '#eevee-choices',
  };

  const NOISE = /run-menu|btn-shop|pokechain|settings|typechart|pokedex|achievements|credits|patch/i;

  // Interactive layers the engine builds straight onto document.body, which are
  // NOT `.screen` elements and therefore invisible to anything that only walks
  // `.screen`. The item-equip modal was the first of these we hit; it was fixed
  // by name, and the lesson did not generalise — `#eevee-choice-overlay` (a real
  // 2-8 way evolution choice) and `#egg-overlay` are the same trap. Both are
  // `await`ed by the engine, so they do not merely hide a choice, they stall the
  // run until something clicks.
  //
  // Matched by SHAPE rather than by id, so the next one is caught too: a visible
  // element sitting directly under <body>, painted over the page. The named
  // exclusions are the decorative layers that are not interactive.
  // `tutorial` is ours: browser.py hides that layer outright, and a hidden
  // element cannot be a decision. Listed anyway so the two never depend on each
  // other's ordering again.
  const OVERLAY_SKIP = /weather|maint|typechart|tutorial|^sl-/;

  const overlays = () => [...document.body.children].filter((e) => {
    const id = e.id || '';
    const cls = typeof e.className === 'string' ? e.className : '';
    if (!/overlay/.test(id + ' ' + cls) || OVERLAY_SKIP.test(id + ' ' + cls)) return false;
    if (!shown(e)) return false;
    const cs = getComputedStyle(e);
    return cs.position === 'fixed' || cs.position === 'absolute';
  });

  window.__pk_layer = () => {
    // Overlays sit on top of everything, so they are read first: whatever screen
    // is behind one is not what the player is being asked about.
    const ov = overlays()[0];
    if (ov) return { kind: 'overlay', id: ov.id || 'overlay' };
    for (const id of CFG.modals) {
      if (shown(document.getElementById(id))) return { kind: 'modal', id };
    }
    const s = [...document.querySelectorAll('.screen')]
      .find((e) => getComputedStyle(e).display !== 'none');
    return { kind: 'screen', id: s ? s.id : '(none)' };
  };

  // Single source of truth for the action list: __pk_apply indexes into exactly
  // this array, so a choice can never end up pointing at a different button.
  const choiceElements = () => {
    const L = window.__pk_layer();
    if (L.kind === 'screen' && L.id === 'map-screen') return { L, nodes: true };
    const sel = (L.kind === 'modal' || L.kind === 'overlay')
      ? (CONTAINERS[L.id] || '#' + L.id)
      : (CONTAINERS[L.id] || '#' + L.id);
    const root = document.querySelector(sel) || document.getElementById(L.id);
    if (!root) return { L, els: [] };
    let els = [...root.querySelectorAll(
      '.poke-card, .choice-card, .trainer-card, .item-card, .equip-pokemon-row button, button'
    )].filter((e) => shown(e) && !e.disabled && !NOISE.test(e.id + ' ' + e.className));

    // Nothing matched, but the layer is one the player may be expected to act
    // on. The engine does not always build options out of buttons or known
    // classes: the branching-evolution options are bare `div`s made with inline
    // styles, and the elite-prep bag is a row of `span.item-badge`.
    //
    // Falling back to every visible child is too greedy, and it showed: the
    // evolution ANIMATION (`#evo-overlay`) has children too, so a random bot was
    // offered "What? Squirtle is evolving!" and "slot1" as a choice and spent a
    // decision on it. What separates a real option is that the engine made it
    // clickable — `cursor: pointer` is in the inline style it writes for the
    // branching choice, and absent from anything merely being animated.
    if (!els.length && (L.kind === 'overlay' || L.kind === 'modal')) {
      els = [...root.children].filter((e) => {
        if (!shown(e)) return false;
        const cls = typeof e.className === 'string' ? e.className : '';
        if (NOISE.test(e.id + ' ' + cls)) return false;
        return getComputedStyle(e).cursor === 'pointer' || e.tagName === 'BUTTON'
          || e.getAttribute('role') === 'button';
      });
    }
    return { L, els };
  };

  // A button's own text is sometimes useless on its own. The equip modal shows
  // five buttons all reading "EQUIP", one per team member, and which Pokemon
  // each belongs to lives in the row around it. A bot reading only labels cannot
  // tell them apart, so it has to guess — which is a silent, invisible handicap.
  // Where a button sits in a row carrying the context, we label it with that.
  const ROW_SELECTOR = '.equip-pokemon-row, .swap-choice, .poke-card';

  // Sprite fallbacks are not game data, and they must not reach a bot.
  //
  // When an image fails to load the engine writes a pictograph in its place --
  // "🤍 Silk Scarf" for an item whose icon is missing. Whether it is there
  // depends on a 404 coming back, so the SAME decision reads two different ways
  // depending on timing, and differently again on a machine whose copy of site/
  // has different holes. `mirror --phase verify` exists because copies do differ.
  //
  // That made runs unrepeatable. A bot reading labels -- which the linear feature
  // sets do -- gets a different vector, picks a different option, and the run
  // walks off from there. It cost a benchmark row of 8 badges that could never be
  // reproduced, and it is why README's claim that a missing sprite cannot change
  // a run was not true.
  //
  // Astral-plane pictographs only (U+1F000 and up), so a shiny's ★ survives: that
  // one IS the engine telling us something about the run.
  const PICTOGRAPH = /[\u{1F000}-\u{1FAFF}\u{FE0F}]/gu;
  const clean = (s) => s.replace(PICTOGRAPH, '').replace(/\s+/g, ' ').trim();

  const labelFor = (e) => {
    const own = clean(e.innerText || '');
    const row = e.closest && e.closest(ROW_SELECTOR);
    if (row && row !== e) {
      const context = clean(row.innerText || '');
      // "Squirtle Lv5 — empty — EQUIP" says which button this is; "EQUIP" does not.
      if (context && context !== own) return `${own} — ${context}`.slice(0, 160);
    }
    return own.slice(0, 160);
  };

  window.__pk_choices = () => {
    const { L, nodes, els } = choiceElements();
    if (nodes) {
      const st = g('state');
      if (!st || !st.map) return [];
      return Object.values(st.map.nodes)
        .filter((n) => n.accessible && !n.visited)
        .sort((a, b) => (a.layer - b.layer) || (a.col - b.col))
        .map((n) => ({ kind: 'node', id: n.id, node: n.type, layer: n.layer, col: n.col }));
    }
    return (els || []).map((e, i) => ({
      kind: 'element', idx: i, layer: L.id, id: e.id || null,
      label: labelFor(e),
    }));
  };

  // A cheap fingerprint of what the player is being asked: which layer, and
  // which options. Used to tell whether the engine has reacted to the last
  // action yet — see `__pk_await_change`.
  window.__pk_sig = () => {
    const L = window.__pk_layer();
    return L.id + '#' + window.__pk_choices().map((c) => c.id || c.idx || c.label).join(',');
  };

  // Wait for the engine to leave the decision point named by `sig`.
  //
  // SAFE as a poller predicate, unlike `__pk_pump`: it only reads. It never
  // clicks, so it cannot change the order in which the engine draws its seeded
  // Math.random, which is the property the whole settle design protects.
  //
  // This replaces a flat 70 ms sleep after every action. Measured, the page
  // reacts in 0.4 ms median and 3.5 ms at worst, so the sleep was two orders of
  // magnitude too long — but it could not simply be shortened, because what it
  // was really buying was that `__pk_settle` does not read the OLD screen, see a
  // decision still standing there, and hand a stale state back as if the action
  // had not happened. Waiting for the change is that guarantee, and it is
  // adaptive: instant on a fast machine, still correct on a slow one.
  //
  // The cap exists for an action that leaves the question unchanged. None was
  // observed in fifty steps, and if one exists the caller simply carries on as
  // it did before.
  window.__pk_await_change = async (sig, capMs) => {
    if (!sig) return 0;
    const now = window.__pk_realNow || performance.now.bind(performance);
    const t0 = now();
    while (now() - t0 < capMs) {
      if (window.__pk_sig() !== sig) return now() - t0;
      await new Promise((k) => window.__pk_realTimeout(k, 1));
    }
    return -1;
  };

  window.__pk_apply = (c) => {
    // Read BEFORE acting: what the player was being asked. Returned so the
    // caller can wait for the engine to leave it without a second round trip.
    const before = window.__pk_sig();
    if (c.kind === 'node') {
      const st = g('state');
      const n = st && st.map && st.map.nodes[c.id];
      if (!n || !n.accessible || n.visited) return false;
      g('onNodeClick')(n); // async by design; Python waits for the change
      return { ok: true, sig: before };
    }
    const { els } = choiceElements();
    const el = els && els[c.idx];
    if (!el) return false;
    el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
    return { ok: true, sig: before };
  };

  window.__pk_point = () => {
    const L = window.__pk_layer();
    if (L.kind === 'screen' && CFG.terminal.includes(L.id)) return 'terminal';
    if (L.kind === 'modal') return 'decision';
    // An overlay is a decision only if it actually offers a choice. The egg
    // reveal offers none — it just waits for a tap — so it is transient and
    // __pk_advance dismisses it. Deciding by what is on it rather than by its
    // id is what makes an unknown overlay behave sensibly instead of hanging.
    if (L.kind === 'overlay') {
      return window.__pk_choices().length > 1 ? 'decision' : 'transient';
    }
    return CFG.decision.includes(L.id) ? 'decision' : 'transient';
  };

  // Advances anything that is not a decision by itself: battle playback,
  // level-up banners, "Continue" buttons.
  window.__pk_advance = () => {
    for (const id of ['btn-continue-battle', 'btn-auto-battle']) {
      const b = document.getElementById(id);
      if (b && getComputedStyle(b).display !== 'none' && !b.disabled) { b.click(); return id; }
    }
    const L = window.__pk_layer();
    // A click-to-continue overlay has no button to press: the handler is on the
    // layer itself, so dismissing it means clicking the layer.
    if (L.kind === 'overlay') {
      const el = overlays()[0];
      if (el) {
        const one = [...el.querySelectorAll('button')].filter((b) => shown(b) && !b.disabled);
        (one.length === 1 ? one[0] : el)
          .dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
        return L.id;
      }
    }
    const root = document.getElementById(L.id);
    if (!root) return null;
    const btns = [...root.querySelectorAll('button')]
      .filter((b) => shown(b) && !b.disabled && !NOISE.test(b.id + ' ' + b.className));
    if (btns.length === 1) { btns[0].click(); return btns[0].id || 'single'; }
    return null;
  };

  // One step of the settle loop: is the game ready, and if not, nudge it.
  //
  // Returns true when there is a real decision to make or the run is over. It
  // has a side effect on purpose — a forced single choice, or a Continue button,
  // is taken here rather than reported back for Python to take.
  //
  // BECAUSE it has side effects, it must never be handed to a poller as a
  // predicate. Call it from `__pk_settle` below, which controls the cadence.
  window.__pk_pump = () => {
    const point = window.__pk_point();
    if (point === 'terminal') return { ready: true, acted: false };
    if (point === 'decision') {
      const n = window.__pk_choices().length;
      if (n > 1) return { ready: true, acted: false };
      if (n === 1) {
        window.__pk_apply(window.__pk_choices()[0]);
        return { ready: false, acted: true };
      }
    }
    return { ready: false, acted: Boolean(window.__pk_advance()) };
  };

  // Run the pump until the game is ready, all inside one call.
  //
  // It must NOT be used as a polling predicate. `__pk_pump` clicks things, and a
  // poller calls its predicate an unpredictable number of times: the clicks then
  // land at different moments, the engine consumes its seeded Math.random in a
  // different order, and the same seed stops replaying the same run. That was a
  // real regression, caught by the determinism test.
  //
  // So the loop lives here, its iteration count driven by the game rather than
  // by a poller, and paced with a real timeout so a click never lands in the
  // middle of the redraw the previous one caused.
  window.__pk_settle = async (timeoutMs) => {
    // __pk_realNow, not performance.now: the page clock is virtual and jumps
    // ahead on every read, so this budget would be spent in a few hundred
    // iterations instead of ninety seconds.
    //
    // The fallback is not defensive clutter, it is the correct reading of the
    // one case that produces it. THIS FILE IS RE-READ FROM DISK ON EVERY RUN
    // while browser.py is a module loaded once, so a long-running process that
    // pulls mid-run gets a new bridge against an old init script -- and an old
    // one does not virtualise the clock at all, which is exactly when
    // performance.now IS the real clock. It cost a training run at episode 78
    // to find that out.
    const now = window.__pk_realNow || performance.now.bind(performance);
    const started = now();
    while (now() - started < timeoutMs) {
      const r = window.__pk_pump();
      if (r.ready) {
        // Reaching a decision is not the same as the decision being finished.
        // Sprites that fail to load are replaced by an emoji a few milliseconds
        // later, so an option's label — which a bot reads, and which the golden
        // fingerprints record — can still be changing under us. Hand back only a
        // question that has stopped moving.
        //
        // This was invisible while every action was followed by a flat 70 ms
        // sleep. It was never the sleep's purpose, just something it happened to
        // cover, which is the trouble with waiting a fixed time for an unnamed
        // reason: remove it and unrelated things break.
        let sig = window.__pk_sig();
        const until = now() + 60;
        while (now() < until) {
          await new Promise((k) => window.__pk_realTimeout(k, 2));
          const again = window.__pk_sig();
          if (again === sig) break;
          sig = again;
        }
        return true;
      }
      // Pace only after actually clicking, so the click never lands on top of
      // the redraw it caused. While merely waiting for the engine's own async
      // work there is nothing to disturb, so check often.
      await new Promise((k) => window.__pk_realTimeout(k, r.acted ? 15 : 2));
    }
    return false;
  };

  // What the screen is asking. Without it a choice can be read backwards: the
  // swap screen lists your team and its prompt is "Choose a Pokémon to
  // release", but a bot seeing only the list may take it for "choose your
  // lead" — and release its best Pokemon believing it promoted it. Observed
  // happening to an LLM, which is what prompted exposing this.
  const promptOf = (id) => {
    const root = document.getElementById(id);
    if (!root) return null;
    const bits = [...root.querySelectorAll('h2, [id$="-prompt"], .screen-desc')]
      .filter(shown)
      .map((e) => (e.innerText || '').replace(/\s+/g, ' ').trim())
      .filter(Boolean);
    return bits.length ? [...new Set(bits)].join(' — ').slice(0, 160) : null;
  };

  // -------------------------------------------------------------------
  // Team order.
  //
  // Slot 0 leads, so the order is a real decision, and until now no bot could
  // make it: the game binds reordering to a hand-rolled pointer drag on the
  // team bar, which lives outside any `.screen`, so `__pk_choices` never saw it.
  //
  // We do NOT simulate the drag. Underneath all the pointer handling the
  // engine's drop does exactly one thing:
  //     [team[a], team[b]] = [team[b], team[a]]; renderTeamBar(team)
  // and the Elite Four prep screen, which has its own drag, mutates that SAME
  // `state.team` array and then calls `window._elitePrepRefresh()`. So one
  // primitive covers both, with no dependence on coordinates or on layout
  // existing, which is what makes it safe headless.
  window.__pk_can_reorder = () => {
    const st = g('state');
    return Boolean(st && Array.isArray(st.team) && st.team.length > 1);
  };

  window.__pk_reorder = (a, b) => {
    const st = g('state');
    if (!st || !Array.isArray(st.team)) return false;
    const t = st.team;
    if (!Number.isInteger(a) || !Number.isInteger(b)) return false;
    if (a === b || a < 0 || b < 0 || a >= t.length || b >= t.length) return false;

    [t[a], t[b]] = [t[b], t[a]];

    // Repaint through whichever renderer owns the screen we are on. Both read
    // the array we just mutated, so a missing one costs the picture, never the
    // swap: the state is already correct either way.
    try {
      if (window.__pk_layer().id === 'elite-prep-screen'
          && typeof window._elitePrepRefresh === 'function') {
        window._elitePrepRefresh();
      } else if (typeof renderTeamBar === 'function') {
        renderTeamBar(t);
      }
    } catch (e) { /* cosmetic only */ }
    return true;
  };

  // The engine's move table and its own move chooser. These are script-global
  // lexical bindings, NOT properties of window: `typeof MOVE_POOL` is 'object'
  // while `window.MOVE_POOL` is undefined, and reading the latter gives no error
  // at all, just silence. That is what `g()` is for.
  const moveOf = (mon) => {
    try {
      const f = g('getMoveForPokemon');
      const m = f && f(mon);
      return m ? { name: m.name, power: m.power, type: m.type, special: !!m.isSpecial } : null;
    } catch (e) { return null; }
  };

  // Pokemon type -> the held item that boosts it (Fire -> charcoal, ...). The
  // one genuinely structured item table the engine exposes: it turns eighteen
  // near-identical "+40% X-type damage" items into one question, "does this
  // match a type I actually field".
  window.__pk_type_items = () => {
    try { return { ...g('TYPE_ITEM_MAP') }; } catch (e) { return null; }
  };

  window.__pk_obs = () => {
    const st = g('state');
    const L = window.__pk_layer();
    const o = { layer: L.kind, screen: L.id, prompt: promptOf(L.id) };
    if (st) {
      o.run = {
        run_seed: st.runSeed, map: st.currentMap, badges: st.badges,
        max_team_size: st.maxTeamSize, nuzlocke: !!st.nuzlockeMode,
        anyone_fainted: !!st.anyFainted, finished: !!st._finished,
        items_this_run: st.itemsThisRun || 0, elite: st.eliteIndex,
      };
      o.team = (st.team || []).map((p) => ({
        uid: p._uid, species_id: p.speciesId, name: p.name, level: p.level,
        hp: p.currentHp, max_hp: p.maxHp, types: p.types, base_stats: p.baseStats,
        move_tier: p.moveTier, item: p.heldItem ? p.heldItem.name : null,
        // The id, not just the name. Every effect in the battle code is keyed on
        // it (heldItem.id === 'leftovers'), and there is no stat or multiplier
        // field anywhere to read instead — so the id is the only stable handle
        // on what an item actually does. `desc` is the English sentence.
        item_id: p.heldItem ? p.heldItem.id : null,
        item_desc: p.heldItem ? p.heldItem.desc : null,
        // The engine's own answer to "what move would this Pokemon use", with
        // power and type. Not derivable from the label, and the move tutor's
        // offer is exactly a comparison against it.
        move: moveOf(p),
        mega_stone: p.megaStone ? p.megaStone.name : null, shiny: !!p.isShiny,
      }));
      o.bag = (st.items || []).map((i) => i && (i.name || i.id));
      // What the move tutor WOULD offer each member. Not guesswork: the engine
      // builds the tutor's button label with exactly this call
      // (doMoveTutorNode -> getBestMove(..., moveTier + 1, ...)), so asking it
      // ourselves gives the offered move with its power and type, which the
      // label does not carry.
      o.offered_moves = {};
      try {
        const best = g('getBestMove');
        if (best) {
          (st.team || []).forEach((p, i) => {
            const m = best(p.types, p.baseStats, p.speciesId, (p.moveTier || 0) + 1, p.heldItem);
            if (m) o.offered_moves[i] = {
              name: m.name, power: m.power, type: m.type, special: !!m.isSpecial,
            };
          });
        }
      } catch (e) { /* older bundle: features fall back to zero */ }
      o.type_items = window.__pk_type_items();
      o.bag_items = (st.items || []).map((i) => i && ({
        id: i.id, name: i.name, desc: i.desc, usable: !!i.usable,
      }));
      if (st.map) {
        o.map = {
          nodes: Object.values(st.map.nodes).map((n) => ({
            id: n.id, kind: n.type, layer: n.layer, col: n.col,
            accessible: !!n.accessible, visited: !!n.visited, revealed: !!n.revealed,
          })),
          edges: st.map.edges.map((e) => [e.from, e.to]),
          current: st.currentNode ? st.currentNode.id : null,
        };
      }
      // Counters accumulated by our runBattle hook (see __pk_attach_score).
      if (window.__pk_stats) o.stats = { ...window.__pk_stats };
    }
    // Reordering is a FREE action: it does not consume the turn, so it is not
    // one of `actions`. Advertised separately, or a bot would have to guess
    // whether the verb applies right now.
    o.can_reorder = window.__pk_can_reorder();
    o.actions = window.__pk_choices();
    return o;
  };

  // ---------------------------------------------------------------------
  // Scoring.
  //
  // The engine already knows how to count (foldBattleIntoRunStats) and how to
  // apply the formula (finalizeRunScore), but it only wires the two together in
  // Challenge mode: the call site reads
  //     state.challengeId && state.runStats && fold(...)
  // so in Story mode the counters would stay at zero forever.
  //
  // Setting challengeId would be the obvious shortcut and it is WRONG: that flag
  // changes the rules, among other things raising the Elite Four's levels
  //     state.challengeId ? Math.max(0, 10 + challengeEliteLevelMod) : 0
  // so the run would no longer be a normal one. Wrapping runBattle leaves the
  // game untouched and still gives us the engine's own counters.
  // ---------------------------------------------------------------------
  window.__pk_attach_score = () => {
    // CAREFUL: no local variable may share a name with a global we intend to
    // replace, or we shadow it and rewrite the wrong copy.
    const foldOrig = g('foldBattleIntoRunStats');
    const newStatsOrig = g('newRunStats');
    const battleOrig = g('runBattle');
    if (typeof battleOrig !== 'function' || typeof foldOrig !== 'function'
        || typeof newStatsOrig !== 'function') {
      return { ok: false, reason: 'scoring functions not found' };
    }
    if (window.__pk_attached) return { ok: true, already: true };

    // Whatever goes wrong here must NOT stop the run: the score is a bonus,
    // the game comes first.
    try {
      const st = g('state');
      if (st && !st.runStats) st.runStats = newStatsOrig();

      // runBattle is a top-level function declaration, so it lives on window
      // and is writable.
      window.runBattle = function (...args) {
        const r = battleOrig.apply(this, args);
        try {
          const s = g('state');
          if (s) {
            if (!s.runStats) s.runStats = newStatsOrig();
            // Same argument order as the engine's own call site:
            //   fold(detailedLog, <runBattle's first argument>, playerWon, pTeam)
            foldOrig(r.detailedLog, args[0], r.playerWon, r.pTeam);
            window.__pk_stats = JSON.parse(JSON.stringify(s.runStats));
          }
        } catch (e) {
          window.__pk_score_error = String(e);
        }
        return r;
      };
      window.__pk_attached = true;
      return { ok: true, mode: 'runBattle-wrapped' };
    } catch (e) {
      return { ok: false, reason: String(e) };
    }
  };

  // Applies the game's official formula to the latest stats snapshot.
  //
  // A note on the time bonus: the formula computes it as 1000 minus 100 per
  // minute of real play, but we freeze Date.now() to make runs reproducible. The
  // upshot is that the bonus sits pinned near 1000 and carries no information.
  // So we also return `points_no_time`, which is the number to use when
  // comparing players or strategies.
  window.__pk_score = (completed) => {
    const fin = g('finalizeRunScore');
    const st = g('state');
    const stats = (st && st.runStats) || window.__pk_stats;
    if (!stats || typeof fin !== 'function') return null;
    const copy = JSON.parse(JSON.stringify(stats));
    const points = fin(copy, { cleared: !!completed });
    const b = copy.scoreBreakdown || {};
    return {
      points,
      points_no_time: points - (b.timeBonus || 0),
      breakdown: b,
      stats: copy,
    };
  };
})();
