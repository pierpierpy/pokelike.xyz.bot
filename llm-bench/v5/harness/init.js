// Runs before the game bundle. Pins the game's two sources of randomness
// (Date.now and Math.random) and collapses animation delays via a virtual
// performance.now clock.
//
// The run seed is `Date.now() ^ (Math.random() * 2**32)`, so pinning both is
// what makes runs reproducible. Changing a constant here voids every recorded
// score (every seed maps to a different run).
//
// `__PK_CFG_JSON__` is substituted by browser.py with str.replace before
// injection.

(() => {
  const cfg = __PK_CFG_JSON__;
  let s = (cfg.seed >>> 0) || 1;
  Math.random = function () {
    s ^= s << 13; s >>>= 0; s ^= s >> 17; s ^= s << 5; s >>>= 0;
    return s / 4294967296;
  };
  let clock = 1700000000000;
  Date.now = () => (clock += 16);
  const st = window.setTimeout.bind(window);
  // Kept for the settle loop, which needs a real timeout to pace itself.
  window.__pk_realTimeout = st;
  window.setTimeout = (fn, d, ...a) => st(fn, Math.min(Number(d) || 0, cfg.max_delay), ...a);
  window.requestAnimationFrame = (fn) => st(() => fn(performance.now()), 0);

  // Virtual performance.now: jumps `tick` ms on every read to collapse
  // animations. Without this, ~79% of a headless run is waiting on the battle
  // screen for an outcome already decided. __pk_realNow keeps the true clock
  // for the settle loop's timeout budget.
  // tick = 0 leaves the clock alone (used by --watch for human viewing).
  window.__pk_realNow = performance.now.bind(performance);
  if (cfg.tick > 0) {
    let vnow = window.__pk_realNow();
    performance.now = () => (vnow += cfg.tick);
  }
  try { localStorage.clear(); } catch (e) {}
})();
