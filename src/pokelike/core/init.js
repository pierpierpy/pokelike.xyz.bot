// Runs BEFORE the game bundle. Pins the game's two sources of randomness and
// collapses animation delays.
//
// The run seed is `Date.now() ^ (Math.random() * 2**32)` and everything a run
// generates (map layout, encounters, item offers) flows from the engine's PRNG
// seeded with it. Making a run reproducible therefore means pinning both, which
// is why this file is the one place where an edit does not mark a recorded score
// but voids it: change the initial clock or the shifts below and every seed maps
// to a different run, so a benchmark still answers, and answers about a game
// nobody else can replay.
//
// `__PK_CFG_JSON__` is substituted by browser.py before injection. Done with
// str.replace and not `%`, because this file is mostly prose and one comment
// mentioning a percentage made `INIT_SCRIPT % cfg` raise "not enough arguments
// for format string" from a line nowhere near the change.

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
  // Kept aside because the line below caps every delay to 1 ms: the settle loop
  // needs a real one to pace itself, or it clicks faster than the game redraws.
  window.__pk_realTimeout = st;
  window.setTimeout = (fn, d, ...a) => st(fn, Math.min(Number(d) || 0, cfg.max_delay), ...a);
  window.requestAnimationFrame = (fn) => st(() => fn(performance.now()), 0);

  // The clock the ANIMATIONS read, and the reason capping timers was not enough.
  //
  // The engine plays a battle out over roughly 800 ms, and it paces that on
  // elapsed time rather than on a number of ticks: it asks what time it is and
  // works out how far along it should be. Capping setTimeout to 1 ms only makes
  // it ask more often; the answer still walks at wall-clock speed, so we sat
  // watching an animation whose outcome was already decided. Measured: 79% of a
  // headless run was that wait, and 98.6% of it on the battle screen.
  //
  // Moving the clock forward by `tick` on every read collapses it. `__pk_realNow`
  // keeps a true one for anything that must measure real elapsed time -- the
  // settle loop's own timeout budget, which would otherwise burn 90 seconds in
  // a few hundred reads.
  //
  // tick = 0 leaves the clock alone, which is what --watch does: a person
  // watching wants to see the battle.
  window.__pk_realNow = performance.now.bind(performance);
  if (cfg.tick > 0) {
    let vnow = window.__pk_realNow();
    performance.now = () => (vnow += cfg.tick);
  }
  try { localStorage.clear(); } catch (e) {}
})();
