/*
 * API layer. The UI only talks to QF.api, never to fetch or the mocks directly.
 *
 * Mode is chosen from the page URL:
 *   index.html                                    -> mock data (default)
 *   index.html?api=live                           -> real backend, same origin
 *   index.html?api=live&base=http://localhost:5000 -> real backend on another origin
 *   index.html?latency=fast                       -> mock data with near-zero latency
 */
(() => {
  "use strict";
  const QF = (window.QF = window.QF || {});

  const params = new URLSearchParams(window.location.search);
  const mode = params.get("api") === "live" ? "live" : "mock";
  const base = (params.get("base") || "").replace(/\/+$/, "");
  const TIMEOUT_MS = 30000;

  async function request(path, { method = "GET", body } = {}) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
    try {
      const res = await fetch(base + path, {
        method,
        headers: body
          ? { Accept: "application/json", "Content-Type": "application/json" }
          : { Accept: "application/json" },
        body: body ? JSON.stringify(body) : undefined,
        signal: controller.signal,
      });
      if (!res.ok) throw new Error(`HTTP ${res.status} from ${path}`);
      return await res.json();
    } catch (err) {
      if (err.name === "AbortError") throw new Error(`Timed out after ${TIMEOUT_MS / 1000}s on ${path}`);
      throw err;
    } finally {
      clearTimeout(timer);
    }
  }

  function checkBits(data) {
    if (!data || !Array.isArray(data.bits) || data.bits.length === 0 || data.bits.some((b) => b !== 0 && b !== 1)) {
      throw new Error("Response did not contain a bits array of 0s and 1s");
    }
    return data;
  }

  function checkStat(data) {
    if (!data || typeof data.pass !== "boolean" || typeof data.score !== "number") {
      throw new Error("Response did not contain pass and score");
    }
    return data;
  }

  const live = {
    getQuantumDraw: () => request("/quantum-draw").then(checkBits),
    getClassicalDraw: () => request("/classical-draw").then(checkBits),
    replayClassical: (seed) =>
      request("/classical-draw/replay", { method: "POST", body: { seed } }).then(checkBits),
    getStatTest: (source) => request(`/stat-test?source=${encodeURIComponent(source)}`).then(checkStat),
  };

  const mock = {
    getQuantumDraw: () => QF.mock.quantumDraw().then(checkBits),
    getClassicalDraw: () => QF.mock.classicalDraw().then(checkBits),
    replayClassical: (seed) => QF.mock.classicalReplay({ seed }).then(checkBits),
    getStatTest: (source) => QF.mock.statTest(source).then(checkStat),
  };

  QF.api = { mode, base, ...(mode === "live" ? live : mock) };
})();
