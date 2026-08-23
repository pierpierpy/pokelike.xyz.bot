// Runs before the game bundle. Pins the game's two sources of randomness and
// collapses animation delays.
//
// The run seed is `Date.now() ^ (Math.random() * 2**32)` and the engine's PRNG
// drives everything from that seed. Pinning both Date.now and Math.random is
// what makes a run reproducible; any edit here changes what every seed produces.
//
// `__PK_CFG_JSON__` is substituted by browser.py before injection via
// str.replace (not Python's `%` operator, which conflicts with prose comments).

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
  // Preserved so the settle loop can use a real timeout; the line below caps
  // every delay to 1 ms.
  window.__pk_realTimeout = st;
  window.setTimeout = (fn, d, ...a) => st(fn, Math.min(Number(d) || 0, cfg.max_delay), ...a);
  window.requestAnimationFrame = (fn) => st(() => fn(performance.now()), 0);

  // The virtual clock that collapses animation time.
  //
  // The engine paces battles by elapsed time, not tick count, so capping
  // setTimeout alone does not help. Advancing performance.now by `tick` ms on
  // every read collapses an 800 ms animation to a few iterations.
  //
  // `__pk_realNow` keeps a true clock for the settle loop's timeout budget.
  // tick = 0 leaves the clock alone (used by --watch so a person sees the battle).
  window.__pk_realNow = performance.now.bind(performance);
  if (cfg.tick > 0) {
    let vnow = window.__pk_realNow();
    performance.now = () => (vnow += cfg.tick);
  }
  try { localStorage.clear(); } catch (e) {}
})();
