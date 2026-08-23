// Runs before the game bundle. Pins Math.random and Date.now so the run seed
// (Date.now() ^ (Math.random() * 2**32)) is deterministic, and collapses
// animation delays.
//
// Editing this file voids recorded scores rather than merely marking them:
// changing the clock or PRNG shifts maps every seed to a different run.
//
// `__PK_CFG_JSON__` is substituted by browser.py via str.replace before injection.

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
  // Preserved uncapped for the settle loop, which needs real timing.
  window.__pk_realTimeout = st;
  window.setTimeout = (fn, d, ...a) => st(fn, Math.min(Number(d) || 0, cfg.max_delay), ...a);
  window.requestAnimationFrame = (fn) => st(() => fn(performance.now()), 0);

  // Virtual performance.now: advances by `tick` ms on every read, collapsing
  // animation waits. `__pk_realNow` keeps the true clock for the settle loop's
  // timeout budget. tick=0 leaves the clock alone (used by --watch).
  window.__pk_realNow = performance.now.bind(performance);
  if (cfg.tick > 0) {
    let vnow = window.__pk_realNow();
    performance.now = () => (vnow += cfg.tick);
  }
  try { localStorage.clear(); } catch (e) {}
})();
