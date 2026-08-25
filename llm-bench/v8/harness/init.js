// Runs before the game bundle. Pins Math.random (seeded xorshift), Date.now
// (frozen clock advancing 16 ms per read), and collapses animation delays.
// Changing this file voids every recorded result because the same seed would
// map to a different run.
//
// `__PK_CFG_JSON__` is substituted by browser.py via str.replace (not `%`,
// because comments in this file would break format-string parsing).

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
  // Original setTimeout, needed by the settle loop (which cannot use the capped one).
  window.__pk_realTimeout = st;
  window.setTimeout = (fn, d, ...a) => st(fn, Math.min(Number(d) || 0, cfg.max_delay), ...a);
  window.requestAnimationFrame = (fn) => st(() => fn(performance.now()), 0);

  // Virtual performance.now: advances `tick` ms on every read, collapsing
  // animations the engine paces by elapsed time. __pk_realNow keeps the true
  // clock for the settle loop's timeout budget. tick=0 leaves it alone (--watch).
  window.__pk_realNow = performance.now.bind(performance);
  if (cfg.tick > 0) {
    let vnow = window.__pk_realNow();
    performance.now = () => (vnow += cfg.tick);
  }
  try { localStorage.clear(); } catch (e) {}
})();
