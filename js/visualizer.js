/*
 * Quantum visualizer: one large superposition bar plus a strip of per-bit cells.
 *
 * States (set as data-state on the figure and the strip):
 *   superposition  idle, the bar is a live 50/50 mix
 *   measuring      a draw is in flight
 *   collapsed-0    the first measured bit was 0, the bar snapped to the 0 side
 *   collapsed-1    the first measured bit was 1, the bar snapped to the 1 side
 *
 * All motion lives in styles.css and uses only transform and opacity.
 */
(() => {
  "use strict";
  const QF = (window.QF = window.QF || {});

  const MAX_CELLS = 64;
  const STAGGER_BUDGET_MS = 800;
  const UNCOLLAPSE_MS = 250;
  const COLLAPSE_SETTLE_MS = 420 + STAGGER_BUDGET_MS + 200;
  const REDUCED_SETTLE_MS = 150;

  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

  const TEXT = {
    superposition: "In superposition: 50% 0 \u00b7 50% 1",
    measuring: "Measuring\u2026",
    collapsed: (bit) => `Measured: ${bit}`,
  };

  class Visualizer {
    constructor({ figure, strip, stateLine, stripLabel }) {
      this.figure = figure;
      this.strip = strip;
      this.stateLine = stateLine;
      this.stripLabel = stripLabel;
      this.flash = figure.querySelector(".qviz-flash");
      this.cells = [];
      this.collapsed = false;
      this.buildCells(MAX_CELLS);
      this.setState("superposition");
    }

    get reduced() {
      return reduceMotion.matches;
    }

    buildCells(count) {
      this.strip.textContent = "";
      this.cells = [];
      const step = Math.min(12, STAGGER_BUDGET_MS / count);
      for (let i = 0; i < count; i++) {
        const cell = document.createElement("span");
        cell.className = "qcell";
        cell.style.setProperty("--delay", `${Math.round(i * step)}ms`);
        const face = document.createElement("span");
        face.className = "qcell-face";
        cell.appendChild(face);
        this.strip.appendChild(cell);
        this.cells.push(cell);
      }
    }

    setState(state) {
      this.figure.dataset.state = state;
      this.strip.dataset.state = state;
      if (state !== "measuring") this.setLong(false);
    }

    setLong(on) {
      this.figure.dataset.long = String(on);
      this.strip.dataset.long = String(on);
    }

    clearCells() {
      for (const cell of this.cells) {
        cell.dataset.bit = "";
        cell.firstChild.textContent = "";
      }
    }

    /** Return to superposition before a new measurement. Resolves when the bar has settled. */
    prepare() {
      if (!this.collapsed) return Promise.resolve();
      this.collapsed = false;
      this.setState("superposition");
      this.clearCells();
      this.stateLine.textContent = TEXT.superposition;
      return wait(this.reduced ? 0 : UNCOLLAPSE_MS);
    }

    /** Called only once a request has been pending for 100ms. */
    setMeasuring() {
      this.setState("measuring");
      this.stateLine.textContent = TEXT.measuring;
    }

    /** Snap the bar to bits[0] and collapse each strip cell in turn. */
    collapse(bits) {
      const shown = bits.slice(0, MAX_CELLS);
      if (shown.length !== this.cells.length) this.buildCells(shown.length);
      this.stripLabel.textContent =
        bits.length > MAX_CELLS
          ? `Showing the first ${MAX_CELLS} of ${bits.length} measurements. Each square is one bit.`
          : `${bits.length} measurements per draw. Each square is one bit.`;

      this.collapsed = true;
      const first = bits[0];
      this.setState(`collapsed-${first}`);
      this.stateLine.textContent = TEXT.collapsed(first);

      if (!this.reduced && this.flash) {
        this.flash.classList.remove("is-on");
        void this.flash.offsetWidth; // restart the one-shot flash animation
        this.flash.classList.add("is-on");
      }

      shown.forEach((bit, i) => {
        const cell = this.cells[i];
        cell.dataset.bit = String(bit);
        cell.firstChild.textContent = String(bit);
      });

      return wait(this.reduced ? REDUCED_SETTLE_MS : COLLAPSE_SETTLE_MS);
    }

    /** Back to idle after a failed draw. */
    reset() {
      this.collapsed = false;
      this.setState("superposition");
      this.clearCells();
      this.stateLine.textContent = TEXT.superposition;
    }
  }

  QF.Visualizer = Visualizer;
})();
