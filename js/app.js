/*
 * Page wiring: panels, output logs, loader timing, seed validation, stat badges.
 * Talks to the backend only through QF.api (see api.js).
 */
(() => {
  "use strict";
  const QF = window.QF;
  const api = QF.api;
  const $ = (id) => document.getElementById(id);
  const params = new URLSearchParams(window.location.search);

  const SEED_MAX = 4294967295;
  const MAX_LOG = 10;
  const SPINNER_AFTER_MS = 100; // nothing is shown for waits shorter than this
  const SKELETON_AFTER_MS = 1000; // skeletons only for long waits

  /* ---------- helpers ---------- */

  function withLoading(promise, { onSpinner, onSkeleton } = {}) {
    const spinnerTimer = setTimeout(() => onSpinner && onSpinner(), SPINNER_AFTER_MS);
    const skeletonTimer = setTimeout(() => onSkeleton && onSkeleton(), SKELETON_AFTER_MS);
    const done = () => {
      clearTimeout(spinnerTimer);
      clearTimeout(skeletonTimer);
    };
    return promise.then(
      (value) => {
        done();
        return value;
      },
      (err) => {
        done();
        throw err;
      }
    );
  }

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
  }

  function bitsElement(bits) {
    const wrap = el("div", "bits");
    for (let i = 0; i < bits.length; i += 8) {
      wrap.appendChild(el("span", "byte", bits.slice(i, i + 8).join("")));
    }
    return wrap;
  }

  function countMatches(a, b) {
    const total = Math.min(a.length, b.length);
    let same = 0;
    for (let i = 0; i < total; i++) if (a[i] === b[i]) same++;
    return { same, total };
  }

  /* ---------- panel ---------- */

  const STAT_TEXT = {
    idle: ["–", () => "Not tested yet"],
    testing: ["", () => "Testing…"],
    pass: ["✓", (s) => `Pass · score ${s}`],
    fail: ["✕", (s) => `Fail · score ${s}`],
    error: ["!", () => "Test unavailable"],
  };

  class Panel {
    constructor(prefix, source) {
      this.source = source;
      this.root = $(`${prefix}-panel`);
      this.list = $(`${prefix}-log`);
      this.empty = $(`${prefix}-log-empty`);
      this.status = $(`${prefix}-status`);
      this.stat = $(`${prefix}-stat`);
      this.error = $(`${prefix}-error`);
      this.errorText = $(`${prefix}-error-text`);
      this.errorDetail = $(`${prefix}-error-detail`);
      this.retry = $(`${prefix}-retry`);
      this.buttons = Array.from(this.root.querySelectorAll("[data-action]"));
      this.busy = false;
      this.statToken = 0;
      this.retryAction = null;
      this.retry.addEventListener("click", () => this.retryAction && this.retryAction());
    }

    async run({ button, request, onSpinner, onSkeleton, onSuccess, onFail, errorText, retryLabel, retryAction }) {
      if (this.busy) return;
      this.busy = true;
      this.hideError();
      for (const b of this.buttons) if (b !== button) b.setAttribute("aria-disabled", "true");

      let skeleton = null;
      const clearLoading = () => {
        button.classList.remove("is-busy");
        button.removeAttribute("aria-busy");
        if (skeleton) skeleton.remove();
        skeleton = null;
        this.syncEmpty();
      };

      try {
        const data = await withLoading(request(), {
          onSpinner: () => {
            button.classList.add("is-busy");
            button.setAttribute("aria-busy", "true");
            if (onSpinner) onSpinner();
          },
          onSkeleton: () => {
            skeleton = this.addSkeleton();
            if (onSkeleton) onSkeleton();
          },
        });
        clearLoading();
        await onSuccess(data);
      } catch (err) {
        clearLoading();
        if (onFail) onFail(err);
        this.showError(errorText, err, retryLabel, retryAction);
        console.error(err);
      } finally {
        for (const b of this.buttons) b.removeAttribute("aria-disabled");
        this.busy = false;
      }
    }

    addEntry({ title, meta = [], bits, note, cracked = false }) {
      const li = el("li", cracked ? "log-entry log-entry--cracked" : "log-entry");
      const head = el("div", "log-meta");
      head.appendChild(el("strong", "log-title-text", title));
      if (cracked) head.appendChild(el("span", "chip", "Predicted"));
      for (const m of meta) head.appendChild(el("span", null, m));
      li.appendChild(head);
      if (bits) li.appendChild(bitsElement(bits));
      if (note) li.appendChild(el("p", "log-note", note));
      this.list.prepend(li);
      while (this.list.children.length > MAX_LOG) this.list.lastElementChild.remove();
      this.syncEmpty();
    }

    addSkeleton() {
      const li = el("li", "log-entry log-entry--skeleton");
      li.setAttribute("aria-hidden", "true");
      li.append(el("span", "skeleton-line"), el("span", "skeleton-line skeleton-line--short"));
      this.list.prepend(li);
      this.syncEmpty();
      return li;
    }

    syncEmpty() {
      const hasEntries = this.list.children.length > 0;
      this.empty.hidden = hasEntries;
      this.list.hidden = !hasEntries;
    }

    announce(message) {
      this.status.textContent = "";
      setTimeout(() => {
        this.status.textContent = message;
      }, 50);
    }

    showError(text, err, retryLabel, retryAction) {
      this.errorText.textContent = text;
      this.errorDetail.textContent = err && err.message ? err.message : "";
      this.retry.querySelector(".btn-label").textContent = retryLabel;
      this.retryAction = retryAction;
      this.error.hidden = false;
      this.announce(text);
    }

    hideError() {
      this.error.hidden = true;
      this.retryAction = null;
    }

    setStat(state, score) {
      const [glyph, text] = STAT_TEXT[state];
      this.stat.dataset.state = state;
      this.stat.querySelector(".stat-glyph").textContent = glyph;
      this.stat.querySelector(".stat-text").textContent = text(typeof score === "number" ? score.toFixed(2) : "");
    }

    runStatTest() {
      const token = ++this.statToken;
      const current = () => token === this.statToken;
      withLoading(api.getStatTest(this.source), {
        onSpinner: () => current() && this.setStat("testing"),
      }).then(
        (r) => current() && this.setStat(r.pass ? "pass" : "fail", r.score),
        (err) => {
          if (current()) this.setStat("error");
          console.error(err);
        }
      );
    }
  }

  /* ---------- classical ---------- */

  const classical = new Panel("c", "classical");
  const cRun = $("c-run");
  const cReplay = $("c-replay");
  const seedForm = $("c-seed-form");
  const seedInput = $("c-seed");
  const seedError = $("c-seed-error");
  const seedHistory = new Map(); // seed -> { label, bits }
  let cDrawCount = 0;

  function validateSeed(raw, { requireValue = false } = {}) {
    const value = raw.trim();
    if (value === "") {
      return requireValue ? { ok: false, message: "Enter a seed, or run a draw first." } : { ok: true, empty: true };
    }
    if (!/^\d+$/.test(value)) return { ok: false, message: "Use whole numbers only, like 1234." };
    const n = Number(value);
    if (n > SEED_MAX) return { ok: false, message: `Use a seed of ${SEED_MAX} or less.` };
    return { ok: true, value: n };
  }

  function setSeedError(message) {
    seedError.textContent = message;
    if (message) seedInput.setAttribute("aria-invalid", "true");
    else seedInput.removeAttribute("aria-invalid");
  }

  // Validate when the field loses focus, not on every keystroke.
  seedInput.addEventListener("blur", () => {
    const r = validateSeed(seedInput.value);
    setSeedError(r.ok ? "" : r.message);
  });
  // Once an error is showing, clear it the moment the value becomes valid.
  seedInput.addEventListener("input", () => {
    if (seedError.textContent && validateSeed(seedInput.value).ok) setSeedError("");
  });

  function runClassicalDraw() {
    return classical.run({
      button: cRun,
      request: () => api.getClassicalDraw(),
      onSuccess: (data) => {
        cDrawCount += 1;
        const label = `draw ${cDrawCount}`;
        // Accept 1234 or "1234" so a backend that serializes the seed as a string still works.
        const seed = data.seed == null || data.seed === "" ? NaN : Number(data.seed);
        const hasSeed = Number.isInteger(seed) && seed >= 0;
        if (hasSeed) seedHistory.set(seed, { label, bits: data.bits });
        classical.addEntry({
          title: `Draw ${cDrawCount}`,
          meta: [hasSeed ? `Seed ${seed}` : "Seed missing", `${data.bits.length} bits`],
          bits: data.bits,
        });
        if (hasSeed) {
          seedInput.value = String(seed);
          setSeedError("");
        }
        classical.announce(
          hasSeed
            ? `Draw ${cDrawCount} complete: ${data.bits.length} bits from seed ${seed}.`
            : `Draw ${cDrawCount} complete: ${data.bits.length} bits. The backend sent no seed.`
        );
        classical.runStatTest();
      },
      errorText: "Couldn't reach the classical generator.",
      retryLabel: "Retry Draw",
      retryAction: runClassicalDraw,
    });
  }

  function runReplay() {
    const check = validateSeed(seedInput.value, { requireValue: true });
    if (!check.ok) {
      setSeedError(check.message);
      seedInput.focus();
      return Promise.resolve();
    }
    setSeedError("");
    const seed = check.value;

    return classical.run({
      button: cReplay,
      request: () => api.replayClassical(seed),
      onSuccess: (data) => {
        const original = seedHistory.get(seed);
        if (original) {
          const { same, total } = countMatches(original.bits, data.bits);
          const all = same === total && original.bits.length === data.bits.length;
          classical.addEntry({
            title: `Replay of ${original.label}`,
            meta: [`Seed ${seed}`, `${data.bits.length} bits`],
            bits: data.bits,
            cracked: all,
            note: all
              ? `${same} of ${total} bits match ${original.label}. Anyone who knows the seed can predict every bit.`
              : `${same} of ${total} bits match ${original.label}.`,
          });
          classical.announce(`Replay complete: ${same} of ${total} bits match ${original.label}.`);
        } else {
          seedHistory.set(seed, { label: `the first replay of seed ${seed}`, bits: data.bits });
          classical.addEntry({
            title: `Replay of seed ${seed}`,
            meta: [`${data.bits.length} bits`],
            bits: data.bits,
            note: "No earlier draw used this seed. Replay it again and the same bits come back.",
          });
          classical.announce(`Replay of seed ${seed} complete.`);
        }
      },
      errorText: `Couldn't replay seed ${seed}.`,
      retryLabel: "Retry Replay",
      retryAction: runReplay,
    });
  }

  /* ---------- quantum ---------- */

  const quantum = new Panel("q", "quantum");
  const qRun = $("q-run");
  const viz = new QF.Visualizer({
    figure: $("qviz"),
    strip: $("q-strip"),
    stateLine: $("q-state"),
    stripLabel: $("q-strip-label"),
  });
  let qDrawCount = 0;
  let lastQuantum = null;

  function runQuantumDraw() {
    let prepared = Promise.resolve();
    return quantum.run({
      button: qRun,
      request: () => {
        prepared = viz.prepare();
        return api.getQuantumDraw();
      },
      onSpinner: () => viz.setMeasuring(),
      onSkeleton: () => viz.setLong(true),
      onSuccess: async (data) => {
        await prepared;
        qDrawCount += 1;
        const settled = viz.collapse(data.bits);

        let note;
        if (lastQuantum) {
          const { same, total } = countMatches(lastQuantum.bits, data.bits);
          const pct = Math.round((same / total) * 100);
          note = `${same} of ${total} bits match draw ${lastQuantum.draw} (${pct}%). Pure chance gives about 50%.`;
        } else {
          note = "Run another draw and compare. There is no seed to replay.";
        }
        quantum.addEntry({
          title: `Draw ${qDrawCount}`,
          meta: ["No seed", `${data.bits.length} bits`],
          bits: data.bits,
          note,
        });
        lastQuantum = { draw: qDrawCount, bits: data.bits };
        quantum.announce(`Draw ${qDrawCount} complete. The first qubit measured ${data.bits[0]}.`);
        quantum.runStatTest();
        await settled;
      },
      onFail: () => viz.reset(),
      errorText: "Couldn't reach the quantum generator.",
      retryLabel: "Retry Draw",
      retryAction: runQuantumDraw,
    });
  }

  /* ---------- page ---------- */

  cRun.addEventListener("click", runClassicalDraw);
  qRun.addEventListener("click", runQuantumDraw);
  seedForm.addEventListener("submit", (event) => {
    event.preventDefault();
    runReplay();
  });

  const sourceNote = $("source-note");
  if (api.mode === "mock") {
    $("mode-tag").hidden = false;
    sourceNote.textContent =
      "Mock data. Quantum bits come from the browser's random generator until the Quantum Rings backend is connected.";
  } else {
    sourceNote.textContent =
      "Quantum bits are measured on Quantum Rings. Classical bits come from a seeded pseudo-random formula.";
  }

  // ?autorun=1 plays the full story once (draw, replay, two quantum draws).
  // Used for screenshots and demo recordings.
  async function autorun() {
    await runClassicalDraw();
    await runReplay();
    await runQuantumDraw();
    await runQuantumDraw();
    const root = document.documentElement;
    root.dataset.overflowX = String(root.scrollWidth > root.clientWidth);
    root.dataset.autorun = "done";
  }
  if (params.get("autorun") === "1") autorun();
})();
