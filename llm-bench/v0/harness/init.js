// Runs before the game bundle. Pins the two sources of randomness (Date.now and
// Math.random) so the run seed is deterministic, and collapses animation delays.
//
// `__PK_CFG_JSON__` is substituted by browser.py before injection (via
// str.replace, not %, because prose comments with % would break format strings).

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

  // Virtual clock for animations. The engine paces battles by elapsed time, not
  // tick count, so capping setTimeout alone is not enough. Advancing
  // performance.now by `tick` ms on every read collapses ~800 ms animations.
  // `__pk_realNow` keeps a true clock for the settle loop's timeout budget.
  // tick=0 leaves the clock alone (used by --watch).
  window.__pk_realNow = performance.now.bind(performance);
  if (cfg.tick > 0) {
    let vnow = window.__pk_realNow();
    performance.now = () => (vnow += cfg.tick);
  }
  try { localStorage.clear(); } catch (e) {}
})();
