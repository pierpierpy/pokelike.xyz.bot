// Runs before the game bundle. Pins Math.random and Date.now (the two sources
// the run seed is drawn from) and collapses animation delays.
//
// Editing this file voids recorded scores: changing the initial clock or PRNG
// seed means every seed maps to a different run.
//
// `__PK_CFG_JSON__` is substituted by browser.py before injection (using
// str.replace, not %, because this file contains prose with percent signs).

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

  // Virtual performance clock: advances by `tick` ms per read, collapsing
  // animation time (the engine paces battles on elapsed time, not tick count).
  // `__pk_realNow` keeps the true clock for the settle loop's timeout budget.
  // tick = 0 leaves the clock real (used by --watch).
  window.__pk_realNow = performance.now.bind(performance);
  if (cfg.tick > 0) {
    let vnow = window.__pk_realNow();
    performance.now = () => (vnow += cfg.tick);
  }
  try { localStorage.clear(); } catch (e) {}
})();
