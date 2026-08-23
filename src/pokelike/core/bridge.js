// Bridge between the game engine and Python.
//
// Injected into the page after the game bundle has booted. Exposes functions
// on `window` that Python uses:
//
//   __pk_layer()    which screen or modal is active right now
//   __pk_choices()  the legal actions, as a stable ordered list
//   __pk_apply(c)   perform one of them
//   __pk_obs()      the full state, as plain JSON
(() => {
  // Engine globals are declared with `let`/`function` (script scope, not on
  // `window`), so they require eval to read.
  const g = (n) => { try { return eval(n); } catch (e) { return undefined; } };

  const CFG = window.__PK_CFG;

  const shown = (e) => {
    if (!e) return false;
    const cs = getComputedStyle(e);
    if (cs.display === 'none' || cs.visibility === 'hidden' || cs.opacity === '0') return false;
    const r = e.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };

  // Where each screen keeps its choices; falls back to the screen element itself.
  const CONTAINERS = {
    'starter-screen': '#starter-choices',
    'trainer-screen': '#trainer-choices',
    'catch-screen': '#catch-choices',
    'item-screen': '#item-choices',
    'passive-screen': '#passive-choices',
    'swap-screen': '#swap-choices',
    'eevee-choice-overlay': '#eevee-choices',
  };

  const NOISE = /run-menu|btn-shop|pokechain|settings|typechart|pokedex|achievements|credits|patch/i;

  // Interactive layers the engine builds directly onto document.body, outside
  // any `.screen` element. These include the item-equip modal,
  // `#eevee-choice-overlay` (a 2-8 way evolution choice), and `#egg-overlay`
  // (tap to continue). All are `await`ed, so they stall the run until clicked.
  //
  // Matched by shape (visible, fixed/absolute, overlay in id/class) rather than
  // by id, so new overlays are caught automatically. Named exclusions below are
  // decorative layers that are not interactive.
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
    // Overlays sit on top of everything, so they take priority over screens.
    const ov = overlays()[0];
    if (ov) return { kind: 'overlay', id: ov.id || 'overlay' };
    for (const id of CFG.modals) {
      if (shown(document.getElementById(id))) return { kind: 'modal', id };
    }
    const s = [...document.querySelectorAll('.screen')]
      .find((e) => getComputedStyle(e).display !== 'none');
    return { kind: 'screen', id: s ? s.id : '(none)' };
  };

  // Single source of truth for the action list: __pk_apply indexes into this
  // array, so a choice always points at the correct button.
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

    // Nothing matched, but the layer may require player input. The engine does
    // not always use buttons or known classes for options (e.g. branching-evolution
    // choices are bare divs with inline styles).
    //
    // Falling back to every visible child is too greedy because non-interactive
    // layers (like the evolution animation) also have children. The distinguishing
    // feature of a real option is `cursor: pointer` in its computed style.
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

  // When a button's own text is ambiguous (e.g. five "EQUIP" buttons), the
  // containing row carries the context. labelFor reads the row text to
  // disambiguate.
  const ROW_SELECTOR = '.equip-pokemon-row, .swap-choice, .poke-card';

  // Sprite fallbacks must not reach a bot.
  //
  // When an image fails to load the engine writes a pictograph in its place
  // (e.g. "🤍 Silk Scarf"). Whether the fallback appears depends on a 404, so
  // the same decision produces different labels depending on which images are
  // present in site/. Stripping astral-plane pictographs (U+1F000+) removes
  // these non-deterministic prefixes. A shiny's ★ is kept because the engine
  // uses it as real game data.
  const PICTOGRAPH = /[\u{1F000}-\u{1FAFF}\u{FE0F}]/gu;
  const clean = (s) => s.replace(PICTOGRAPH, '').replace(/\s+/g, ' ').trim();

  const labelFor = (e) => {
    const own = clean(e.innerText || '');
    const row = e.closest && e.closest(ROW_SELECTOR);
    if (row && row !== e) {
      const context = clean(row.innerText || '');
      // The full row context disambiguates which button this is.
      if (context && context !== own) return `${own} — ${context}`.slice(0, 160);
    }
    return own.slice(0, 160);
  };

  // Tooltip text for map nodes: the trainer's archetype and types, a gym
  // leader's roster, what a trade or item node does. Read via the engine's own
  // `getNodeLabel(node)` function (the same one that builds the DOM tooltip).
  //
  // Cached per (seed, map) because the labels do not change while walking a map;
  // visited status is already tracked in `state`.
  const tipText = (html) => {
    if (!html) return null;
    // Each roster line is its own <div>. Since the element is detached,
    // innerText does not insert breaks automatically, so separators are added
    // manually.
    const spaced = String(html)
      .replace(/<\s*br\s*\/?>/gi, "\u0001")
      .replace(/<\s*\/\s*(div|p|li|tr)\s*>/gi, "\u0001");
    const box = document.createElement('div');
    box.innerHTML = spaced;
    return (box.innerText || box.textContent || "")
      .split("\u0001").map((s) => s.replace(/\s+/g, ' ').trim())
      .filter(Boolean).join(' | ') || null;
  };

  window.__pk_node_tooltips = () => {
    const st = g('state');
    const label = g('getNodeLabel');
    if (!st || !st.map || typeof label !== 'function') return {};
    const key = `${st.runSeed}:${st.currentMap}`;
    window.__pk_tip_cache = window.__pk_tip_cache || {};
    if (window.__pk_tip_cache[key]) return window.__pk_tip_cache[key];

    const out = {};
    Object.values(st.map.nodes).forEach((n) => {
      // Skip unrevealed nodes: the bot should not see what a player cannot.
      if (!n.revealed) return;
      try {
        const t = tipText(label(n));
        if (t) out[n.id] = t;
      } catch (e) { /* one unreadable node is not worth losing the others */ }
    });
    window.__pk_tip_cache[key] = out;
    return out;
  };

  window.__pk_choices = () => {
    const { L, nodes, els } = choiceElements();
    if (nodes) {
      const st = g('state');
      if (!st || !st.map) return [];
      const tips = window.__pk_node_tooltips();
      return Object.values(st.map.nodes)
        .filter((n) => n.accessible && !n.visited)
        .sort((a, b) => (a.layer - b.layer) || (a.col - b.col))
        .map((n) => ({ kind: 'node', id: n.id, node: n.type, layer: n.layer,
                       col: n.col, tooltip: tips[n.id] || null }));
    }
    return (els || []).map((e, i) => ({
      kind: 'element', idx: i, layer: L.id, id: e.id || null,
      label: labelFor(e),
    }));
  };

  // Cheap fingerprint of the current decision point (layer + option ids).
  // Used by __pk_await_change to detect when the engine has reacted.
  window.__pk_sig = () => {
    const L = window.__pk_layer();
    return L.id + '#' + window.__pk_choices().map((c) => c.id || c.idx || c.label).join(',');
  };

  // Wait for the engine to leave the decision point identified by `sig`.
  //
  // Safe as a polling predicate: it only reads, never clicks, so it cannot
  // perturb the engine's seeded PRNG.
  //
  // The cap handles the (unobserved) case where an action leaves the signature
  // unchanged; the caller simply carries on.
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
    // Record the signature before acting so the caller can wait for it to change.
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
    // An overlay is a decision only if it offers more than one choice. Single-
    // or zero-option overlays (like egg reveal) are transient and dismissed by
    // __pk_advance.
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
    // Click-to-continue overlays have no button; the handler is on the layer
    // element itself.
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

  // One step of the settle loop.
  //
  // Returns true when a real decision is pending or the run is over. Has side
  // effects: auto-plays forced single choices and Continue buttons.
  //
  // Must not be used as a polling predicate because the side effects can
  // perturb the engine's seeded PRNG ordering.
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
  // The loop lives here (not in a poller) because __pk_pump has side effects:
  // a poller calls its predicate an unpredictable number of times, which would
  // cause clicks to land non-deterministically and break seed reproducibility.
  // Each iteration is paced with a real timeout so a click does not land during
  // the redraw the previous one caused.
  window.__pk_settle = async (timeoutMs) => {
    // Use __pk_realNow (not performance.now) because the page clock is virtual
    // and advances on every read, which would exhaust the budget in a few hundred
    // iterations.
    //
    // The fallback covers the case where this bridge is injected without a
    // matching init.js (e.g. a long-running process pulled a new bridge mid-run).
    // When init.js has not virtualized the clock, performance.now is already real.
    const now = window.__pk_realNow || performance.now.bind(performance);
    const started = now();
    while (now() - started < timeoutMs) {
      const r = window.__pk_pump();
      if (r.ready) {
        // Wait for the decision's labels to stabilize. Sprites that fail to
        // load are replaced by an emoji a few milliseconds later, which can
        // change an option's label while the signature is being read.
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
      // Pace after clicking so the click does not overlap the previous redraw.
      // When merely waiting (no click), poll frequently.
      await new Promise((k) => window.__pk_realTimeout(k, r.acted ? 15 : 2));
    }
    return false;
  };

  // The screen's prompt text (e.g. "Choose a Pokémon to release"). Without it,
  // a bot cannot distinguish a swap-to-release from a swap-to-lead.
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
  // Slot 0 leads the next battle. The game binds reordering to a pointer drag
  // on the team bar (outside any `.screen`). Rather than simulating the drag,
  // the swap is applied directly to `state.team` and the relevant renderer is
  // called. The Elite Four prep screen uses the same array, so one primitive
  // covers both surfaces.
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

    // Repaint through whichever renderer owns the current screen. A missing
    // renderer only costs the visual; the state is already correct.
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

  // The engine's move table and move chooser are script-global lexical bindings
  // (not on `window`), accessed via the `g()` eval helper.
  const moveOf = (mon) => {
    try {
      const f = g('getMoveForPokemon');
      const m = f && f(mon);
      return m ? { name: m.name, power: m.power, type: m.type, special: !!m.isSpecial } : null;
    } catch (e) { return null; }
  };

  // Pokemon type -> the held item that boosts it (e.g. Fire -> charcoal).
  // The one structured item table the engine exposes.
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
        // The item id is the stable handle the battle code keys effects on
        // (e.g. heldItem.id === 'leftovers'). `desc` is the English tooltip.
        item_id: p.heldItem ? p.heldItem.id : null,
        item_desc: p.heldItem ? p.heldItem.desc : null,
        // The engine's own answer to "what move would this Pokemon use", with
        // power and type. Useful for comparing against a move tutor's offer.
        move: moveOf(p),
        mega_stone: p.megaStone ? p.megaStone.name : null, shiny: !!p.isShiny,
      }));
      o.bag = (st.items || []).map((i) => i && (i.name || i.id));
      // What the move tutor would offer each member. Calls the same function
      // the engine uses to build the tutor's button label
      // (getBestMove(..., moveTier + 1, ...)).
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
        const tips = window.__pk_node_tooltips();
        o.map = {
          nodes: Object.values(st.map.nodes).map((n) => ({
            id: n.id, kind: n.type, layer: n.layer, col: n.col,
            accessible: !!n.accessible, visited: !!n.visited, revealed: !!n.revealed,
            tooltip: tips[n.id] || null,
          })),
          edges: st.map.edges.map((e) => [e.from, e.to]),
          current: st.currentNode ? st.currentNode.id : null,
        };
      }
      // Counters accumulated by our runBattle hook (see __pk_attach_score).
      if (window.__pk_stats) o.stats = { ...window.__pk_stats };
    }
    // Reordering is a free action (does not consume the turn), so it is
    // advertised separately from `actions`.
    o.can_reorder = window.__pk_can_reorder();
    o.actions = window.__pk_choices();
    return o;
  };

  // ---------------------------------------------------------------------
  // Scoring.
  //
  // The engine has foldBattleIntoRunStats (counting) and finalizeRunScore
  // (formula), but only wires them together in Challenge mode. Setting
  // challengeId would bypass this but also changes the rules (raises Elite Four
  // levels), so instead runBattle is wrapped to call the counting function on
  // every battle result while leaving the game mode untouched.
  // ---------------------------------------------------------------------
  window.__pk_attach_score = () => {
    // Do not name locals the same as globals being replaced (causes shadowing).
    const foldOrig = g('foldBattleIntoRunStats');
    const newStatsOrig = g('newRunStats');
    const battleOrig = g('runBattle');
    if (typeof battleOrig !== 'function' || typeof foldOrig !== 'function'
        || typeof newStatsOrig !== 'function') {
      return { ok: false, reason: 'scoring functions not found' };
    }
    if (window.__pk_attached) return { ok: true, already: true };

    // Errors here must not stop the run; scoring is a bonus.
    try {
      const st = g('state');
      if (st && !st.runStats) st.runStats = newStatsOrig();

      // runBattle is a top-level function declaration, writable on `window`.
      window.runBattle = function (...args) {
        const r = battleOrig.apply(this, args);
        try {
          const s = g('state');
          if (s) {
            if (!s.runStats) s.runStats = newStatsOrig();
            // Same argument order as the engine's own call site.
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
  // The time bonus is pinned near 1000 because Date.now() is frozen, so
  // `points_no_time` is the meaningful comparison number.
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
