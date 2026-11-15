/*
 * QuantumFair mock backend.
 * Returns data in the exact shapes of the agreed API contract so the UI can be
 * built and tested before the real backend exists.
 *
 *   GET  /quantum-draw               -> { bits: [0,1,...], source: "quantum" }
 *   GET  /classical-draw             -> { bits: [...], seed: 1234, source: "classical" }
 *   POST /classical-draw/replay      { seed } -> same bits as the original draw
 *   GET  /stat-test?source=...       -> { pass: true, score: 0.87 }
 *
 * The mock "quantum" bits come from the browser's crypto generator. They are a
 * placeholder, not quantum output. The UI labels mock mode on screen.
 */
(() => {
  "use strict";
  const QF = (window.QF = window.QF || {});

  const BITS_PER_DRAW = 64;
  const params = new URLSearchParams(window.location.search);
  const FAST = params.get("latency") === "fast";

  // Small, well-known seeded PRNG. Same seed in, same sequence out.
  function mulberry32(seed) {
    let a = seed >>> 0;
    return () => {
      a = (a + 0x6d2b79f5) >>> 0;
      let t = a;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function prngBits(seed, n) {
    const next = mulberry32(seed);
    return Array.from({ length: n }, () => (next() < 0.5 ? 0 : 1));
  }

  function cryptoBits(n) {
    const bytes = new Uint8Array(Math.ceil(n / 8));
    crypto.getRandomValues(bytes);
    return Array.from({ length: n }, (_, i) => (bytes[i >> 3] >> (7 - (i & 7))) & 1);
  }

  function randomInt(min, max) {
    const buf = new Uint32Array(1);
    crypto.getRandomValues(buf);
    return min + (buf[0] % (max - min + 1));
  }

  function latency(minMs, maxMs) {
    const ms = FAST ? randomInt(0, 40) : randomInt(minMs, maxMs);
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  QF.mock = {
    async quantumDraw() {
      // Real Quantum Rings calls have network latency, so the mock is slow on purpose.
      await latency(1200, 2000);
      return { bits: cryptoBits(BITS_PER_DRAW), source: "quantum" };
    },

    async classicalDraw() {
      // Four-digit seeds are easy for a judge to read and retype.
      const seed = randomInt(1000, 9999);
      await latency(250, 400);
      return { bits: prngBits(seed, BITS_PER_DRAW), seed, source: "classical" };
    },

    async classicalReplay({ seed }) {
      await latency(250, 400);
      return { bits: prngBits(seed, BITS_PER_DRAW), seed, source: "classical" };
    },

    async statTest(source) {
      await latency(150, 250);
      const score = Math.round((0.8 + Math.random() * 0.15) * 100) / 100;
      return { pass: true, score };
    },

    // Exposed for console checks: QF.mock.prngBits(1234, 64)
    prngBits,
  };
})();
