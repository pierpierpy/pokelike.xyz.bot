// Bridge between the game engine and Python.
//
// Injected after the game bundle. Exposes functions on `window`:
//
//   __pk_layer()    which screen or modal is active
//   __pk_choices()  the legal actions, in stable order
//   __pk_apply(c)   perform one
//   __pk_obs()      the full state as JSON
//
// No pixels are involved; the state is a JS object and buttons are DOM elements.
(() => {
  // Engine globals are `let`/`function` declarations (not on `window`), so
  // they need eval to read.
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
    // The branching-evolution overlay keeps its options in a sub-container.
    'eevee-choice-overlay': '#eevee-choices',
  };

  const NOISE = /run-menu|btn-shop|pokechain|settings|typechart|pokedex|achievements|credits|patch/i;

  // Interactive overlays built directly on document.body (not `.screen` elements).
  // Matched by shape: a visible, positioned element with "overlay" in its id/class.
  // Named exclusions are decorative/non-interactive layers.
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
    // Overlays sit on top, so check them first.
    const ov = overlays()[0];
    if (ov) return { kind: 'overlay', id: ov.id || 'overlay' };
    for (const id of CFG.modals) {
      if (shown(document.getElementById(id))) return { kind: 'modal', id };
    }
    const s = [...document.querySelectorAll('.screen')]
      .find((e) => getComputedStyle(e).display !== 'none');
    return { kind: 'screen', id: s ? s.id : '(none)' };
  };

  // Returns the elements representing legal choices. __pk_apply indexes into
  // exactly this array.
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

    // No standard elements matched. Fall back to visible children with
    // cursor:pointer, which the engine sets on clickable branching-choice divs.
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

  // A button's label may be ambiguous on its own (e.g. five "EQUIP" buttons).
  // When the button sits in a row that carries context, label it with that.
  const ROW_SELECTOR = '.equip-pokemon-row, .swap-choice, .poke-card';

  // Strip sprite-fallback pictographs from labels. When an image 404s, the
  // engine writes a pictograph in its place, making the same label read
  // differently depending on which files exist on disk. Only astral-plane
  // codepoints (U+1F000+) are stripped; a shiny's ★ is engine data and stays.
  const PICTOGRAPH = /[\u{1F000}-\u{1FAFF}\u{FE0F}]/gu;
  const clean = (s) => s.replace(PICTOGRAPH, '').replace(/\s+/g, ' ').trim();

  const labelFor = (e) => {
    const own = clean(e.innerText || '');
    const row = e.closest && e.closest(ROW_SELECTOR);
    if (row && row !== e) {
      const context = clean(row.innerText || '');
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

  // A fingerprint of the current decision point (layer + options). Used by
  // __pk_await_change to detect when the engine has reacted.
  window.__pk_sig = () => {
    const L = window.__pk_layer();
    return L.id + '#' + window.__pk_choices().map((c) => c.id || c.idx || c.label).join(',');
  };

  // Wait for the engine to leave the decision point identified by `sig`.
  // Safe as a poller predicate because it only reads, never clicks.
  // The cap handles the (unobserved) case where an action does not change the sig.
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
    // Capture the sig before acting so the caller can wait for it to change.
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
    // An overlay is a decision only if it offers more than one choice.
    // Single-option overlays (like egg reveal) are transient.
    if (L.kind === 'overlay') {
      return window.__pk_choices().length > 1 ? 'decision' : 'transient';
    }
    return CFG.decision.includes(L.id) ? 'decision' : 'transient';
  };

  // Advances non-decision screens: battle playback, level-up banners, Continue.
  window.__pk_advance = () => {
    for (const id of ['btn-continue-battle', 'btn-auto-battle']) {
      const b = document.getElementById(id);
      if (b && getComputedStyle(b).display !== 'none' && !b.disabled) { b.click(); return id; }
    }
    const L = window.__pk_layer();
    // A click-to-continue overlay has its handler on the layer itself.
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

  // One step of the settle loop. Returns true when the game is ready for a
  // decision or the run is over. Has side effects (auto-plays forced choices),
  // so it must not be used as a poller predicate.
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

  // Run the pump in a loop until the game is ready. The iteration count is
  // driven by the game, not a poller, and paced with real timeouts so clicks
  // do not land during redraws (which would disturb the seeded PRNG order).
  window.__pk_settle = async (timeoutMs) => {
    // Uses __pk_realNow because performance.now is virtual and would exhaust
    // the budget in a few hundred iterations. The fallback handles the case
    // where init.js did not virtualise the clock (e.g. a mismatched pair after
    // a mid-run pull).
    const now = window.__pk_realNow || performance.now.bind(performance);
    const started = now();
    while (now() - started < timeoutMs) {
      const r = window.__pk_pump();
      if (r.ready) {
        // Wait for the decision's labels to stabilize (sprites that fail to load
        // get replaced by emoji a few ms later, changing the label text).
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
      // Pace after clicking to avoid landing on top of the redraw.
      await new Promise((k) => window.__pk_realTimeout(k, r.acted ? 15 : 2));
    }
    return false;
  };

  // The screen's prompt text (e.g. "Choose a Pokemon to release"), which
  // disambiguates what the action list means.
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
  // Team order. Slot 0 leads the next battle.
  //
  // The engine binds reorder to a pointer drag on the team bar; underneath,
  // the drop is just a swap: `[team[a], team[b]] = [team[b], team[a]]`.
  // One primitive covers both the team bar and the Elite Four prep screen.
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

    // Repaint whichever renderer owns the current screen. A missing renderer
    // only costs the visual; the state is already correct.
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

  // The engine's move table and move chooser. These are script-global lexical
  // bindings (not on `window`), accessed via `g()`.
  const moveOf = (mon) => {
    try {
      const f = g('getMoveForPokemon');
      const m = f && f(mon);
      return m ? { name: m.name, power: m.power, type: m.type, special: !!m.isSpecial } : null;
    } catch (e) { return null; }
  };

  // Pokemon type -> held item that boosts it (e.g. Fire -> charcoal).
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
        // The item id, not just the name. Battle code keys effects on it
        // (e.g. heldItem.id === 'leftovers').
        item_id: p.heldItem ? p.heldItem.id : null,
        item_desc: p.heldItem ? p.heldItem.desc : null,
        // The engine's assigned move with power and type.
        move: moveOf(p),
        mega_stone: p.megaStone ? p.megaStone.name : null, shiny: !!p.isShiny,
      }));
      o.bag = (st.items || []).map((i) => i && (i.name || i.id));
      // What the move tutor would offer each team member, with power and type
      // (which the tutor's button label does not carry).
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
    // Reordering is a free action (does not consume the turn), advertised
    // separately from the action list.
    o.can_reorder = window.__pk_can_reorder();
    o.actions = window.__pk_choices();
    return o;
  };

  // ---------------------------------------------------------------------
  // Scoring.
  //
  // The engine wires foldBattleIntoRunStats to finalizeRunScore only in Challenge
  // mode. Setting challengeId would change difficulty (Elite Four levels), so
  // instead we wrap runBattle to call the engine's own counter after each battle.
  // ---------------------------------------------------------------------
  window.__pk_attach_score = () => {
    const foldOrig = g('foldBattleIntoRunStats');
    const newStatsOrig = g('newRunStats');
    const battleOrig = g('runBattle');
    if (typeof battleOrig !== 'function' || typeof foldOrig !== 'function'
        || typeof newStatsOrig !== 'function') {
      return { ok: false, reason: 'scoring functions not found' };
    }
    if (window.__pk_attached) return { ok: true, already: true };

    // Errors here must not stop the run; the score is secondary.
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

  // Apply the engine's score formula. Also returns `points_no_time` because the
  // time bonus is pinned near 1000 (Date.now is frozen) and carries no info.
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
