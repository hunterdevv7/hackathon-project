/* QuantumFair page logic.
 *
 * Every random number on this page comes from the Flask backend:
 *   seeded PRNG  GET  /classical-draw, POST /classical-draw/replay   (the problem)
 *   quantum      GET  /quantum-draw, GET /quantum-state             (the fix, via Quantum Rings)
 *   checks       POST /stat-test, POST /attack, GET /engine
 * Nothing is faked in the browser. If the API is down, the page says so and waits.
 *
 * The live demo has one slot machine with a switch. The switch decides what spins
 * the reels: the seeded PRNG or a Quantum Rings draw. Spin and Replay work the same
 * way on both, which is the point: replay reproduces one and not the other.
 */
(function () {
  'use strict';

  // ---------------------------------------------------------------- API
  // ?api= wins. Otherwise try the server that sent this page (python -m backend.app),
  // then the default port, so the page also works when opened from disk or from
  // another dev server such as VS Code Live Server.
  const API_CANDIDATES = (function () {
    const q = new URLSearchParams(location.search).get('api');
    if (q) return [q.replace(/\/$/, '')];
    const list = [];
    if (location.protocol.startsWith('http')) list.push('');
    list.push('http://localhost:5000', 'http://127.0.0.1:5000');
    return list;
  })();
  let API = API_CANDIDATES[0];

  async function findApi() {
    for (const base of API_CANDIDATES) {
      try {
        const res = await fetch(base + '/health', { cache: 'no-store' });
        const data = await res.json();
        if (data && data.status === 'ok') { API = base; return true; }
      } catch (err) { /* try the next one */ }
    }
    return false;
  }

  function ApiError(message, status) { this.message = message; this.status = status; }

  async function api(path, body) {
    const init = body === undefined ? {} : {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body)
    };
    let res;
    try {
      res = await fetch(API + path, init);
    } catch (err) {
      // The server may have moved (restarted, or this page came from elsewhere): look again once.
      if (await findApi()) {
        try { res = await fetch(API + path, init); } catch (err2) { /* still down */ }
      }
      if (!res) {
        set({ apiOffline: true });
        throw new ApiError('the API isn’t reachable', 0);
      }
    }
    if (S.apiOffline) { set({ apiOffline: false }); loadEngine(); }
    let data = null;
    try { data = await res.json(); } catch (err) { /* not JSON */ }
    if (!res.ok) throw new ApiError((data && data.error) || 'HTTP ' + res.status, res.status);
    return data;
  }

  // ---------------------------------------------------------------- helpers
  const $ = (id) => document.getElementById(id);
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  const clamp01 = (x) => (x < 0 ? 0 : x > 1 ? 1 : x);
  const pad4 = (n) => String(n).padStart(4, '0');
  const fmt = (n) => n.toLocaleString('en-US');
  const pct = (x) => Math.round(x * 100) + '%';
  const reelText = (v) => (v ? v.join(' · ') : '— · — · —');

  /** Three reel digits from a run: the first 30 bits as a number, last three decimal digits. */
  function reelDigits(bits) {
    let v = 0;
    for (let i = 0; i < 30 && i < bits.length; i++) v = v * 2 + bits[i];
    return String(v % 1000).padStart(3, '0').split('').map(Number);
  }

  function parseSeed(text) {
    const t = String(text).trim().replace(/,/g, '');
    if (!/^\d{1,4}$/.test(t)) return null;
    return parseInt(t, 10);
  }

  function probZero(theta) {
    if (theta === 90) return 0.5;
    const c = Math.cos(theta * Math.PI / 360);
    return c * c;
  }

  const isPole = (theta) => theta === 0 || theta === 180;

  function matchCount(a, b) {
    let m = 0;
    for (let i = 0; i < 64 && i < a.length && i < b.length; i++) if (a[i] === b[i]) m++;
    return m;
  }

  // ---------------------------------------------------------------- state
  /** One record per source: the first run (A) and the replay (B) the page compares. */
  const emptyRun = () => ({ bitsA: null, bitsB: null, valsA: null, valsB: null, stat: null, seed: null, theta: 90, typed: false });

  const S = {
    apiOffline: false,
    engine: null,          // GET /engine
    src: 'classical',      // the switch: 'classical' | 'quantum'
    runs: { classical: emptyRun(), quantum: emptyRun() },
    // the machine (shared by both sources)
    ang: [-252, -252, -252], dur: [0, 0, 0], vals: [7, 7, 7],
    spinning: false, spinMode: null, landed: false, lever: false, err: '',
    seedDraft: '', spinSec: 1.2, shots: 256,
    // the qubits behind the reels in quantum mode
    qPhase: 'super', qResult: null, qDrag: false, theta: 90, qEngine: null, qMs: null,
    qState: null,          // GET /quantum-state for the current theta
    // page
    rail: 0, motion: true,
    // the turn
    tBeat: -1, tBit: null, tCount: 0, tEngine: null, tErr: '',
    // attack
    atkC: null, atkQ: null, atkBusy: false, atkErr: '',
    // the crack card
    crackRuns: [], crackErr: ''
  };

  let renderQueued = false;
  function set(patch) {
    Object.assign(S, patch);
    if (!renderQueued) { renderQueued = true; requestAnimationFrame(() => { renderQueued = false; render(); }); }
  }
  function setRun(src, patch) {
    set({ runs: Object.assign({}, S.runs, { [src]: Object.assign({}, S.runs[src], patch) }) });
  }

  // ---------------------------------------------------------------- build repeated parts
  function buildParts() {
    document.querySelectorAll('[data-faces]').forEach((reel) => {
      const capR = reel.querySelector('.cap.r');
      for (let d = 0; d < 10; d++) {
        const f = document.createElement('div');
        f.className = 'rf f' + d;
        f.style.color = d === 7 ? '#B3261B' : '#1C1512';
        f.innerHTML = '<span class="rd">' + d + '</span>';
        reel.insertBefore(f, capR);
      }
    });
    document.querySelectorAll('[data-bulbs]').forEach((row) => {
      const slow = row.dataset.bulbs === 'slow';
      for (let i = 0; i < 12; i++) {
        const b = document.createElement('span');
        b.className = 'bulb';
        b.style.animationDelay = (slow ? (i % 6) * 0.4 : i * 0.05).toFixed(2) + 's';
        row.appendChild(b);
      }
    });
    document.querySelectorAll('[data-sphere]').forEach((s) => {
      const rings = ['', 'q-m1', 'q-m2', 'q-m3', 'q-m4', 'q-m5', 'q-eq', 'q-p1', 'q-p2', 'q-p3', 'q-p4'];
      const arrow = s.querySelector('[data-arrow]');
      rings.forEach((c) => {
        const r = document.createElement('div');
        r.className = ('q-ring ' + c).trim();
        s.insertBefore(r, arrow);
      });
      ['q-axis', 'q-axis b'].forEach((c) => {
        const a = document.createElement('div');
        a.className = c;
        s.insertBefore(a, arrow);
      });
      arrow.innerHTML = '<div class="q-shaft"></div><div class="q-shaft b"></div><div class="q-tip"></div><div class="q-tip b"></div><div class="q-tip c"></div>';
    });
    document.querySelectorAll('[data-squares]').forEach((row) => {
      for (let i = 0; i < 64; i++) row.appendChild(document.createElement('span'));
    });
    const runs = $('crack-runs');
    for (let n = 1; n <= 3; n++) {
      const row = document.createElement('div');
      row.style.cssText = 'display:flex; align-items:center; gap:14px';
      const cell = 'width:42px; height:48px; display:flex; align-items:center; justify-content:center; background:#E4DCCB; font-family:\'Newsreader\',Georgia,serif; font-weight:600; font-size:30px; line-height:1';
      row.innerHTML = '<span style="width:48px; flex:none; font-size:14px; color:#5B4F47">Pull ' + n + '</span>' +
        '<div style="display:flex; gap:4px"><span style="' + cell + '">·</span><span style="' + cell + '">·</span><span style="' + cell + '">·</span></div>' +
        '<span style="font-size:14px; font-weight:600; color:#8E1D16"></span>';
      runs.appendChild(row);
    }
  }

  function paintSquares(key, bits, on, off, empty) {
    const cells = document.querySelector('[data-squares="' + key + '"]').children;
    for (let i = 0; i < 64; i++) cells[i].style.background = bits && i < bits.length ? (bits[i] ? on : off) : empty;
  }

  function paintHits(key, atk, hit, miss, empty) {
    const cells = document.querySelector('[data-squares="' + key + '"]').children;
    for (let i = 0; i < 64; i++) {
      cells[i].style.background = atk && i < atk.actual.length ? (atk.predicted[i] === atk.actual[i] ? hit : miss) : empty;
    }
  }

  // ---------------------------------------------------------------- engine
  async function loadEngine() {
    try {
      const e = await api('/engine');
      if (!e || typeof e.engine !== 'string') throw new ApiError('not the QuantumFair API', 0);
      set({ engine: e });
      $('api-url').textContent = API || location.origin;
      document.querySelectorAll('.seed-space').forEach((el) => { el.textContent = fmt(e.seed_space); });
    } catch (err) { /* banner shows */ }
  }

  // ---------------------------------------------------------------- the crack card: three real replays
  let crackToken = 0;
  async function pullThree(seed) {
    const token = ++crackToken;
    set({ crackRuns: [], crackErr: '' });
    const runs = [];
    for (let i = 0; i < 3; i++) {
      try {
        const r = await api('/classical-draw/replay', { seed: seed, n: 30 });
        if (token !== crackToken) return;
        runs.push(reelDigits(r.bits));
        set({ crackRuns: runs.slice() });
        await wait(140);
      } catch (err) {
        if (token === crackToken) set({ crackErr: 'Couldn’t pull: ' + err.message + '.' });
        return;
      }
    }
  }

  // ---------------------------------------------------------------- the machine
  /** Reel angles that land on `vals`, spinning forward from where the reels are now. */
  function anglesFor(vals, turns) {
    return vals.map((v, i) => {
      const from = S.ang[i] - turns * 360 - i * 360;
      const m = Math.ceil((-from - v * 36) / 360);
      return -(m * 360 + v * 36);
    });
  }

  function setSource(src) {
    if (S.spinning || src === S.src) return;
    const next = { src: src, err: '', landed: true };
    // Show this source's last result on the reels, so they always match the panel.
    const run = S.runs[src];
    const vals = run.valsB || run.valsA;
    if (vals) Object.assign(next, { vals: vals, ang: anglesFor(vals, 1), dur: [0.6, 0.75, 0.9] });
    set(next);
  }

  /** Fetch one run's bits from whichever source the switch is on. */
  function draw(src, mode, typedSeed, n) {
    if (src === 'quantum') return api('/quantum-draw?n=' + n + '&theta=' + S.theta);
    if (mode === 'clock') return api('/classical-draw?n=' + n);
    const seed = mode === 'replay' ? S.runs.classical.seed : typedSeed;
    return api('/classical-draw/replay', { seed: seed, n: n });
  }

  async function spin(mode, typedSeed) {
    if (S.spinning) return;
    const src = S.src, run = S.runs[src], n = S.shots;
    if (mode === 'replay' && !run.bitsA) return;
    const quantum = src === 'quantum';
    set({ spinning: true, spinMode: mode, landed: false, lever: true, err: '' });
    setTimeout(() => set({ lever: false }), 420);
    if (quantum) set({ qPhase: 'collapsing', qResult: null });

    const t0 = performance.now();
    let data;
    try {
      data = await draw(src, mode, typedSeed, n);
    } catch (err) {
      const why = quantum
        ? (err.status === 503 ? 'The Quantum Rings engine is unavailable: ' : 'The quantum draw failed: ') + err.message + '. No bits were faked.'
        : 'The PRNG draw failed: ' + err.message + '.';
      set({ spinning: false, landed: true, err: why, qPhase: quantum ? 'super' : S.qPhase });
      return;
    }
    const ms = Math.round(performance.now() - t0);
    const statReq = api('/stat-test', { bits: data.bits }).catch(() => null);

    // Replay means "compare with run A". For the PRNG that's the same seed again
    // (typed or not); for qubits it's simply another measurement: there is no seed.
    const replay = quantum
      ? mode === 'replay'
      : mode === 'replay' || (mode === 'typed' && run.bitsA !== null && data.seed === run.seed);
    const vals = reelDigits(data.bits);
    const base = S.spinSec, stagger = base * 0.35;
    set({ ang: anglesFor(vals, 2), dur: [base, base + stagger, base + 2 * stagger] });
    const stat = await Promise.all([statReq, wait((base + 2 * stagger) * 1000 + 180)]).then((r) => r[0]);

    const patch = replay
      ? { bitsB: data.bits, valsB: vals }
      : { bitsA: data.bits, valsA: vals, bitsB: null, valsB: null, stat: stat, typed: mode === 'typed' };
    if (quantum) {
      patch.theta = S.theta;
    } else {
      patch.seed = data.seed;
      if (replay) patch.typed = mode === 'typed';
    }
    setRun(src, patch);
    const next = { spinning: false, landed: true, vals: vals };
    if (!replay) next[quantum ? 'atkQ' : 'atkC'] = null;
    if (quantum) Object.assign(next, { qPhase: 'measured', qResult: data.bits[0], qEngine: data.engine, qMs: ms });
    else next.seedDraft = pad4(data.seed);
    set(next);
  }

  function spinTyped() {
    if (S.src !== 'classical') return;
    const v = parseSeed($('seed-in').value);
    if (v === null) { set({ err: 'Type a whole number from 0 to 9,999. That’s the whole seed space.' }); return; }
    spin('typed', v);
  }

  // ---------------------------------------------------------------- the qubits (theta)
  let stateTimer = 0, stateToken = 0;
  function setTheta(t) {
    const theta = Math.max(0, Math.min(180, Math.round(t)));
    if (S.spinning && S.src === 'quantum') return;
    if (theta === S.theta && S.qPhase !== 'measured') return;
    const next = { theta: theta };
    if (S.qPhase === 'measured') { next.qPhase = 'super'; next.qResult = null; }
    set(next);
    clearTimeout(stateTimer);
    stateTimer = setTimeout(() => loadState(theta), 140);
  }

  /** The qubit's state before measurement, from the engine's statevector. */
  async function loadState(theta) {
    const token = ++stateToken;
    try {
      const d = await api('/quantum-state?n=1&theta=' + theta);
      if (token !== stateToken) return;
      const amps = d.basis_states.map((b) => b.amplitude.re);
      set({ qState: { theta: theta, p0: d.qubits[0].p0, p1: d.qubits[0].p1, a0: amps[0], a1: amps[1], engine: d.engine } });
    } catch (err) {
      if (token === stateToken) set({ qState: { theta: theta, error: err.message } });
    }
  }

  // ---------------------------------------------------------------- the attack
  async function runAttack() {
    const cBits = S.runs.classical.bitsA, qBits = S.runs.quantum.bitsA;
    if (!cBits || !qBits || S.atkBusy) return;
    set({ atkBusy: true, atkErr: '' });
    try {
      const res = await Promise.all([api('/attack', { bits: cBits }), api('/attack', { bits: qBits })]);
      const c = res[0], q = res[1];
      c.actual = cBits.slice(c.known_bits);
      q.actual = qBits.slice(q.known_bits);
      set({ atkC: c, atkQ: q, atkBusy: false });
    } catch (err) {
      set({ atkBusy: false, atkErr: 'The attack request failed: ' + err.message + '.' });
    }
  }

  // ---------------------------------------------------------------- the turn: one real qubit
  let turnToken = 0;
  async function turnBit(again) {
    const token = ++turnToken;
    set({ tBit: null, tErr: '' });
    try {
      const d = await api('/quantum-draw?n=1');
      if (token !== turnToken) return;
      set({ tBit: d.bits[0], tEngine: d.engine, tCount: again ? S.tCount + 1 : S.tCount });
    } catch (err) {
      if (token === turnToken) set({ tErr: err.message });
    }
  }
  function dropTurnBit() { turnToken++; if (S.tBit !== null) set({ tBit: null }); }

  // ---------------------------------------------------------------- scroll scenes (from the design)
  const scene = { scrollMode: false, pinTurn: false, vh: 0, vw: 0, p0: -1, late: null, raf: 0, io: null, els: null };

  function setup() {
    const html = document.documentElement, st = html.style;
    const reduce = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
    const vh = window.innerHeight, vw = window.innerWidth;
    const scrollMode = !reduce && vh >= 420 && vh <= 1600;
    Object.assign(scene, { scrollMode: scrollMode, vh: vh, vw: vw, pinTurn: scrollMode && vw >= 900 && vh >= 680 });
    html.classList.toggle('qf-scroll', scrollMode);
    html.classList.toggle('qf-pin-turn', scene.pinTurn);
    if (scrollMode) st.setProperty('--vh', vh + 'px'); else st.removeProperty('--vh');

    const view = document.querySelector('#top .pin-view'), text = $('o-text'), move = $('o-move');
    if (view && text && move) {
      const vr = view.getBoundingClientRect(), tr = text.getBoundingClientRect();
      const fs = parseFloat(getComputedStyle(move).fontSize) || 13;
      const top = Math.round(tr.bottom - vr.top + 22);
      st.setProperty('--o-top', top + 'px');
      st.setProperty('--o-d', Math.round(vr.height / 2 - (top + 18.5 * fs)) + 'px');
    }

    if (!scrollMode) {
      ['--o-t', '--o-z', '--o-r', '--o-head', '--sp0', '--sp1', '--sp2', '--c-p', '--t-arrow', '--o-px', '--o-py'].forEach((k) => st.removeProperty(k));
      html.removeAttribute('data-late');
      scene.p0 = -1;
      document.querySelectorAll('[data-rv]').forEach((el) => el.setAttribute('data-in', '1'));
      if (S.tBeat !== -1 || S.rail !== 0) set({ tBeat: -1, rail: 0 });
      return;
    }
    if (!scene.io && 'IntersectionObserver' in window) {
      scene.io = new IntersectionObserver((entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) { e.target.setAttribute('data-in', '1'); scene.io.unobserve(e.target); }
        });
      }, { threshold: 0.15 });
      document.querySelectorAll('[data-rv]').forEach((el) => scene.io.observe(el));
    } else if (!scene.io) {
      document.querySelectorAll('[data-rv]').forEach((el) => el.setAttribute('data-in', '1'));
    }
    scene.p0 = -1;
    tick();
  }

  function tick() {
    scene.raf = 0;
    if (!scene.scrollMode || !scene.els) return;
    const vh = scene.vh, html = document.documentElement, st = html.style, E = scene.els;
    const seg = (p, a, b) => clamp01((p - a) / (b - a));
    const ease = (t) => t * t * (3 - 2 * t);
    const out = (t) => 1 - Math.pow(1 - t, 3);

    if (E.open) {
      const r = E.open.getBoundingClientRect();
      const p = clamp01(-r.top / Math.max(1, r.height - vh));
      if (p !== scene.p0) {
        scene.p0 = p;
        st.setProperty('--o-t', ease(seg(p, 0.1, 0.88)).toFixed(4));
        st.setProperty('--o-z', ease(seg(p, 0.14, 0.92)).toFixed(4));
        st.setProperty('--o-r', (1 - ease(seg(p, 0, 0.78))).toFixed(4));
        st.setProperty('--o-head', (1 - seg(p, 0.04, 0.24)).toFixed(3));
        st.setProperty('--sp0', ((1 - out(seg(p, 0, 0.62))) * 1188).toFixed(1) + 'deg');
        st.setProperty('--sp1', ((1 - out(seg(p, 0, 0.74))) * 1512).toFixed(1) + 'deg');
        st.setProperty('--sp2', ((1 - out(seg(p, 0, 0.86))) * 1944).toFixed(1) + 'deg');
        const late = p > 0.24 ? '1' : '0';
        if (late !== scene.late) { scene.late = late; html.setAttribute('data-late', late); }
      }
    }
    if (E.crack) {
      const r = E.crack.getBoundingClientRect();
      st.setProperty('--c-p', clamp01((vh - r.top) / (vh + r.height)).toFixed(4));
    }

    let beat = S.tBeat;
    if (scene.pinTurn && E.turn) {
      const r = E.turn.getBoundingClientRect();
      const p = clamp01(-r.top / Math.max(1, r.height - vh));
      st.setProperty('--t-arrow', (-90 * (1 - ease(seg(p, 0.16, 0.46)))).toFixed(2));
      const nb = p < 0.16 ? 0 : p < 0.58 ? 1 : p < 0.8 ? 2 : 3;
      if (nb !== beat) {
        if (nb >= 2 && beat < 2) turnBit(false);
        if (nb < 2) dropTurnBit();
        beat = nb;
      }
    } else {
      st.removeProperty('--t-arrow');
    }

    let rail = 0;
    for (let i = 0; i < E.ch.length; i++) {
      if (E.ch[i] && E.ch[i].getBoundingClientRect().top <= vh * 0.5) rail = i;
    }
    if (beat !== S.tBeat || rail !== S.rail) set({ tBeat: beat, rail: rail });
  }

  function goBeat(i) {
    const E = scene.els;
    if (scene.pinTurn && E && E.turn) {
      const r = E.turn.getBoundingClientRect();
      const p = [0.06, 0.3, 0.69, 0.9][i];
      window.scrollTo({ top: Math.round(r.top + window.scrollY + p * (r.height - scene.vh)), behavior: 'smooth' });
      return;
    }
    if (i >= 2 && S.tBit === null) turnBit(false);
    if (i < 2) dropTurnBit();
    set({ tBeat: i });
  }

  function parallax(e) {
    if (!scene.scrollMode || scene.p0 < 0 || scene.p0 >= 1 || !S.motion) return;
    const st = document.documentElement.style;
    st.setProperty('--o-px', (e.clientX / window.innerWidth * 2 - 1).toFixed(3));
    st.setProperty('--o-py', (e.clientY / window.innerHeight * 2 - 1).toFixed(3));
  }

  // ---------------------------------------------------------------- dragging (orbit, reels, lever, qubit)
  const orbit = { rx: -6, ry: -18 };
  let reelOff = 0, drag = null, levHandled = false;

  function dragStart(kind, e) {
    if (e.button !== undefined && e.button !== 0) return;
    if (kind === 'orbit' && e.target.closest && e.target.closest('button, input, a')) return;
    if (kind === 'lever' && S.spinning) return;
    const el = e.currentTarget;
    try { el.setPointerCapture(e.pointerId); } catch (err) { /* capture is optional */ }
    const d = { kind: kind, el: el, x0: e.clientX, y0: e.clientY, moved: false };
    if (kind === 'orbit') { d.rx = orbit.rx; d.ry = orbit.ry; el.classList.add('grabbing'); }
    if (kind === 'reels') { d.o = reelOff; el.classList.add('grabbing'); }
    if (kind === 'lever') { d.a = 10; d.arm = $('lever-arm'); d.arm.classList.add('drag'); }
    drag = d;
    if (kind === 'qubit') { set({ qDrag: true }); dragTheta(e, el); }
  }

  function dragMove(e) {
    const d = drag;
    if (!d) return;
    const dx = e.clientX - d.x0, dy = e.clientY - d.y0;
    if (Math.abs(dx) + Math.abs(dy) > 4) d.moved = true;
    const st = document.documentElement.style;
    if (d.kind === 'orbit') {
      orbit.ry = d.ry + dx * 0.4;
      orbit.rx = Math.max(-45, Math.min(30, d.rx - dy * 0.3));
      st.setProperty('--d-rx', orbit.rx.toFixed(1) + 'deg');
      st.setProperty('--d-ry', orbit.ry.toFixed(1) + 'deg');
    } else if (d.kind === 'reels') {
      reelOff = d.o + (dx - dy) * 1.2;
      st.setProperty('--c-o', reelOff.toFixed(1) + 'deg');
    } else if (d.kind === 'lever') {
      d.a = Math.max(-64, Math.min(10, 10 - dy * 0.55));
      d.arm.style.setProperty('--lv-a', d.a.toFixed(1) + 'deg');
    } else if (d.kind === 'qubit') {
      dragTheta(e, d.el);
    }
  }

  function dragEnd(e) {
    const d = drag;
    if (!d) return;
    drag = null;
    if (d.kind === 'orbit' || d.kind === 'reels') d.el.classList.remove('grabbing');
    if (d.kind === 'lever') {
      d.arm.classList.remove('drag');
      d.arm.style.removeProperty('--lv-a');
      levHandled = true;
      setTimeout(() => { levHandled = false; }, 0);
      if (e.type !== 'pointercancel' && (d.a < -36 || !d.moved)) spin('clock');
    }
    if (d.kind === 'qubit') set({ qDrag: false });
  }

  function dragTheta(e, el) {
    const q = el.querySelector('.q') || el;
    const r = q.getBoundingClientRect();
    const c = Math.max(-1, Math.min(1, (r.top + r.height / 2 - e.clientY) / (r.height / 2)));
    setTheta(Math.acos(c) * 180 / Math.PI);
  }

  function bindDrag(el, kind) {
    el.addEventListener('pointerdown', (e) => dragStart(kind, e));
    el.addEventListener('pointermove', dragMove);
    el.addEventListener('pointerup', dragEnd);
    el.addEventListener('pointercancel', dragEnd);
  }

  // ---------------------------------------------------------------- render
  const NEUTRAL = { bg: '#D8D4CC', fg: '#2B2622' };
  const GOOD = { bg: '#BFE3C9', fg: '#10301C' };
  const BAD = { bg: '#F3C3BB', fg: '#5A0F0C' };
  const WAIT = { bg: '#EAD9B0', fg: '#3D2A08' };

  function badge(prefix, b) {
    const label = $(prefix + '-label');
    label.textContent = b.label;
    label.style.background = b.bg;
    label.style.color = b.fg;
    $(prefix + '-detail').textContent = b.detail;
  }

  function statBadge(stat, ran, note) {
    if (!ran) return Object.assign({ label: 'NOT RUN', detail: 'Checks the 0/1 balance and how often bits flip' }, NEUTRAL);
    if (!stat) return Object.assign({ label: 'ERROR', detail: 'The stat test didn’t answer' }, NEUTRAL);
    const t = stat.tests;
    const detail = 'monobit p = ' + t.monobit.p_value.toFixed(3) + ' · runs p = ' + t.runs.p_value.toFixed(3) + ' · passes at p ≥ 0.01' + (note ? ' · ' + note : '');
    return Object.assign({ label: stat.pass ? 'PASS' : 'FAIL', detail: detail }, stat.pass ? GOOD : BAD);
  }

  function text(id, v) { const el = $(id); if (el.textContent !== v) el.textContent = v; }

  /** Words for the status line under the machine. */
  function machineStatus(s, c, q) {
    if (s.err) return { msg: s.err, color: '#F0A79B' };
    if (s.src === 'classical') {
      const m = c.bitsB ? matchCount(c.bitsA, c.bitsB) : 0;
      if (s.spinning) return { msg: s.spinMode === 'replay' ? 'Replaying seed ' + pad4(c.seed) + '…' : 'Pulling. The server picks a seed…', color: '#D9CBC1' };
      if (!c.bitsA) return { msg: 'The server picks a 4-digit seed when you pull.', color: '#D9CBC1' };
      if (!c.bitsB) return { msg: 'Seed ' + pad4(c.seed) + ' captured. Now replay it.', color: '#D9CBC1' };
      if (c.typed) return { msg: 'Cracked by hand. Same seed, same reels, ' + m + '/64 same bits. Now flip the switch to Quantum draw.', color: '#F0A79B' };
      return { msg: 'Cracked. Seed ' + pad4(c.seed) + ' gave identical reels and bits. Now flip the switch to Quantum draw.', color: '#F0A79B' };
    }
    const m = q.bitsB ? matchCount(q.bitsA, q.bitsB) : 0;
    if (s.spinning) return { msg: s.spinMode === 'replay' ? 'No seed to replay. Measuring ' + fmt(s.shots) + ' fresh qubits…' : 'Measuring ' + fmt(s.shots) + ' qubits…', color: '#D9CBC1' };
    if (!q.bitsA) return { msg: 'Each pull measures fresh qubits. There is no seed to capture.', color: '#D9CBC1' };
    if (!q.bitsB) return { msg: 'The qubits landed on ' + reelText(q.valsA) + '. Now try Replay seed.', color: '#D9CBC1' };
    if (isPole(q.theta)) return { msg: 'Same reels again: at θ = ' + q.theta + '° every qubit reads ' + (q.theta === 0 ? '0' : '1') + '. Move θ back toward 90°.', color: '#F0A79B' };
    return { msg: 'No seed to replay. Fresh qubits gave ' + reelText(q.valsB) + ' instead of ' + reelText(q.valsA) + ', and ' + m + '/64 bits matched: chance.', color: '#8FD9B0' };
  }

  function render() {
    const s = S;
    const html = document.documentElement;
    const c = s.runs.classical, q = s.runs.quantum;
    const quantum = s.src === 'quantum';
    const run = quantum ? q : c;

    // chrome
    $('api-banner').hidden = !s.apiOffline;
    text('btn-motion', s.motion ? 'Pause motion' : 'Play motion');
    document.querySelectorAll('.rail a').forEach((a, i) => a.classList.toggle('on', s.rail === i));
    document.querySelectorAll('.shots-text').forEach((el) => { el.textContent = fmt(s.shots); });
    document.querySelectorAll('.shots').forEach((b) => {
      const on = Number(b.dataset.shots) === s.shots;
      b.setAttribute('aria-pressed', String(on));
      b.style.background = on ? '#F4EFE4' : 'transparent';
      b.style.color = on ? '#150B0A' : '#F4EFE4';
    });

    // the crack card
    const rows = $('crack-runs').children;
    for (let i = 0; i < 3; i++) {
      const r = s.crackRuns[i];
      const cells = rows[i].children[1].children;
      for (let j = 0; j < 3; j++) cells[j].textContent = r ? String(r[j]) : '·';
      const same = r && i > 0 && r.join('') === s.crackRuns[0].join('');
      rows[i].children[2].textContent = r && i > 0 ? (same ? 'identical' : 'different') : '';
    }
    text('crack-note', s.crackErr || (s.crackRuns.length === 3
      ? 'Same seed, identical reels. Three separate requests to the server.'
      : 'Same seed, identical reels.'));

    // the turn
    const beat = s.tBeat;
    const tMeasured = beat >= 2 && s.tBit !== null;
    document.querySelectorAll('[data-beat]').forEach((li) => {
      li.classList.toggle('on', beat === -1 || beat === Number(li.dataset.beat));
    });
    const tArrow = $('t-arrow');
    tArrow.classList.toggle('m0', tMeasured && s.tBit === 0);
    tArrow.classList.toggle('m1', tMeasured && s.tBit === 1);
    tArrow.classList.toggle('up', !tMeasured && beat === 0);
    let tKet = '|ψ⟩ = 0.707 |0⟩ + 0.707 |1⟩';
    if (beat === 0) tKet = '|ψ⟩ = |0⟩';
    else if (tMeasured) tKet = '|ψ⟩ = |' + s.tBit + '⟩';
    else if (beat >= 2 && s.tErr) tKet = 'No measurement: ' + s.tErr;
    else if (beat >= 2) tKet = 'Measuring…';
    text('t-ket', tKet);
    text('t-src', tMeasured ? (s.tEngine === 'quantumrings' ? 'Measured through Quantum Rings.' : 'Mock engine, not Quantum Rings.') : '');
    $('t-bit').hidden = !(beat === 3 && s.tBit !== null);
    text('t-bit-text', s.tBit === null ? '' : 'It came out ' + s.tBit + (s.tCount > 0 ? ' (measurement ' + (s.tCount + 1) + ')' : '') + '.');

    // ----- the switch
    document.querySelectorAll('.src-opt').forEach((b) => {
      b.setAttribute('aria-checked', String(b.dataset.src === s.src));
      b.tabIndex = b.dataset.src === s.src ? 0 : -1;
      b.disabled = s.spinning;
    });
    $('machine').classList.toggle('qmode', quantum);
    text('m-marquee', quantum ? 'NO SEED' : 'LUCKY SEED');
    text('m-endpoint', quantum ? '/quantum-draw' : '/classical-draw');

    // ----- the machine
    for (let i = 0; i < 3; i++) {
      const reel = $('reel-' + i);
      const tr = 'transform ' + s.dur[i].toFixed(2) + 's cubic-bezier(.15,.85,.25,1.04)';
      if (reel.style.transition !== tr) reel.style.transition = tr;
      const tf = 'translateZ(-0.8em) rotateX(' + s.ang[i] + 'deg)';
      if (reel.dataset.tf !== tf) { reel.dataset.tf = tf; reel.style.transform = tf; }
    }
    $('lever-arm').classList.toggle('pull', s.lever);
    const replayed = run.bitsB !== null;
    const lights = s.spinning ? 'chase' : (!quantum && replayed && s.landed ? 'flash' : 'idle');
    document.querySelectorAll('.demo-bulbs').forEach((b) => { b.className = 'bulbs demo-bulbs ' + lights; });
    ['btn-spin', 'btn-lever'].forEach((id) => { $(id).disabled = s.spinning; });
    $('btn-typed').disabled = s.spinning || quantum;
    $('btn-replay').disabled = s.spinning || !run.bitsA;
    $('seed-row').hidden = quantum;
    $('no-seed-row').hidden = !quantum;

    if (quantum) {
      text('c-seed', 'none');
      text('c-pred', q.bitsA ? 'nothing to compute' : '— · — · —');
    } else {
      text('c-seed', c.seed === null ? '— — — —' : pad4(c.seed));
      text('c-pred', c.valsA ? reelText(c.valsA) : (s.spinning ? 'computing…' : '— · — · —'));
    }
    text('c-tray', s.landed || !run.bitsA ? s.vals.join(' · ') : '· · ·');
    const seedIn = $('seed-in');
    if (document.activeElement !== seedIn && seedIn.value !== s.seedDraft) seedIn.value = s.seedDraft;
    text('spin-time-text', s.spinSec.toFixed(1) + ' s');
    const st = machineStatus(s, c, q);
    text('c-status', st.msg);
    $('c-status').style.color = st.color;

    // ----- behind the reels
    $('view-classical').hidden = quantum;
    $('view-quantum').hidden = !quantum;
    text('b-title', quantum ? 'The qubits' : 'The generator');
    text('g-seed', c.seed === null ? 'seed' : String(c.seed));
    text('g-n', String(s.shots));
    text('stream-label', quantum ? 'Measurements' : 'Output stream');

    const ph = s.qPhase, measured = ph === 'measured', r = s.qResult, th = s.theta;
    const thDet = isPole(th);
    const fromEngine = s.qState && s.qState.theta === th && !s.qState.error ? s.qState : null;
    const pz = fromEngine ? fromEngine.p0 : probZero(th);
    const w0 = measured ? (r === 0 ? 100 : 0) : Math.round(pz * 1000) / 10;
    const amp0 = fromEngine ? fromEngine.a0 : Math.cos(th * Math.PI / 360);
    const amp1 = fromEngine ? fromEngine.a1 : Math.sin(th * Math.PI / 360);
    let qDigit = '?', qCaption, qDigitColor = '#6F8386';
    let qKet = th === 0 ? '|ψ⟩ = |0⟩' : th === 180 ? '|ψ⟩ = |1⟩' : '|ψ⟩ = ' + amp0.toFixed(3) + ' |0⟩ + ' + amp1.toFixed(3) + ' |1⟩';
    if (ph === 'collapsing') qCaption = 'Measuring as the reels spin…';
    else if (!measured) qCaption = thDet ? 'Plain ' + (th === 0 ? '0' : '1') + '. Already decided.' : 'Not decided until you pull.';
    else { qDigit = String(r); qCaption = 'Collapsed to |' + r + '⟩.'; qKet = '|ψ⟩ = |' + r + '⟩'; qDigitColor = r === 0 ? '#0B6E6A' : '#3F43B5'; }
    text('q-digit', qDigit);
    $('q-digit').style.color = qDigitColor;
    text('q-caption', qCaption);
    text('q-ket', qKet);
    const arrow = $('q-arrow');
    arrow.classList.toggle('m0', measured && r === 0);
    arrow.classList.toggle('m1', measured && r === 1);
    arrow.classList.toggle('drag', s.qDrag);
    arrow.style.transform = 'rotateZ(' + (measured ? (r === 0 ? -90 : 90) : th - 90) + 'deg)';
    const bar = $('q-bar');
    bar.className = 'bar ' + (measured || thDet ? 'det' : 'und');
    bar.setAttribute('aria-label', 'Superposition bar: ' + (measured ? 'collapsed to ' + r : 'probability of 0 is ' + (pz * 100).toFixed(1) + ' percent'));
    $('seg0').style.width = w0 + '%';
    $('seg1').style.width = (100 - w0) + '%';
    text('p0', measured ? (r === 0 ? '100%' : '0%') : (pz * 100).toFixed(1) + '%');
    text('p1', measured ? (r === 1 ? '100%' : '0%') : ((1 - pz) * 100).toFixed(1) + '%');
    let stateSrc = '';
    if (s.qState && s.qState.theta === th && s.qState.error) stateSrc = 'Statevector unavailable: ' + s.qState.error + '.';
    else if (fromEngine) stateSrc = 'Probabilities from the ' + (fromEngine.engine === 'quantumrings' ? 'Quantum Rings' : 'mock') + ' statevector, /quantum-state?theta=' + th + '.';
    text('q-state-src', stateSrc);

    text('theta-text', 'θ = ' + th + '°');
    const qLock = s.spinning && quantum;
    const thetaIn = $('theta');
    if (Number(thetaIn.value) !== th) thetaIn.value = th;
    thetaIn.disabled = qLock;
    document.querySelectorAll('.th').forEach((b) => {
      const on = Number(b.dataset.theta) === th;
      b.setAttribute('aria-pressed', String(on));
      b.style.background = on ? '#0A625F' : 'transparent';
      b.style.color = on ? '#FFFFFF' : '#0A625F';
      b.disabled = qLock;
    });

    // results for the source that's switched on
    const m = replayed ? matchCount(run.bitsA, run.bitsB) : 0;
    const det = quantum && isPole(run.theta);
    if (quantum) {
      paintSquares('rA', run.bitsA, '#0B6E6A', '#B4C6C7', '#D3DEDE');
      paintSquares('rB', run.bitsB, '#0B6E6A', '#B4C6C7', '#D3DEDE');
    } else {
      paintSquares('rA', run.bitsA, '#B3261B', '#E3C9BE', '#D8D4CC');
      paintSquares('rB', run.bitsB, '#B3261B', '#E3C9BE', '#D8D4CC');
    }
    const predictable = !quantum || det;
    text('r-match', replayed ? 'Match ' + m + '/64 · ' + (predictable ? 'predictable' : 'chance level') : (run.bitsA ? 'Awaiting replay' : ''));
    $('r-match').style.color = replayed ? (predictable ? '#8E1D16' : '#0A625F') : '#33474A';
    let note = '';
    if (det && run.bitsA) note = 'every bit is ' + (run.theta === 0 ? '0' : '1') + ': no superposition';
    else if (quantum && run.bitsA && run.theta !== 90) note = 'tests a fair coin; θ = ' + run.theta + '° is biased on purpose';
    badge('rF', statBadge(run.stat, !!run.bitsA, note));
    let rR;
    if (!run.bitsA) rR = Object.assign({ label: 'NOT RUN', detail: quantum ? 'Spin, then replay' : 'Spin, then replay the seed' }, NEUTRAL);
    else if (!replayed) rR = Object.assign({ label: 'READY', detail: 'Press Replay seed' }, WAIT);
    else if (!quantum) rR = Object.assign({ label: 'VULNERABLE', detail: m + '/64 bits identical, same reels' }, BAD);
    else if (det) rR = Object.assign({ label: 'PREDICTABLE', detail: m + '/64 identical. No superposition.' }, BAD);
    else {
      const p = probZero(run.theta);
      rR = Object.assign({ label: 'RESISTANT', detail: m + '/64 matched, chance is ~' + Math.round(64 * (p * p + (1 - p) * (1 - p))) }, GOOD);
    }
    badge('rR', rR);

    // source line
    const e = s.engine;
    let pill, color, line, srcNote;
    if (!quantum) {
      pill = 'Seeded PRNG'; color = '#8E1D16';
      line = 'random.Random(seed) · Python’s Mersenne Twister · seeds 0 to 9,999';
      srcNote = 'Seeds this small are the weak-seed mistake behind real exploits. A 64-bit seed only makes the search longer; the replay still works the moment the seed leaks.';
    } else {
      srcNote = 'Every pull sends a fresh circuit through the Quantum Rings SDK: one qubit per bit, H (or RY(θ)) on each, measured once. Nothing is collected in advance and nothing is reused. Quantum Rings simulates the qubits on this computer, so the demo shows the mechanism, superposition then measurement, with no seed anywhere.';
      if (s.apiOffline) { pill = 'API offline'; color = '#8E1D16'; line = 'Start the backend: python -m backend.app'; }
      else if (!e) { pill = 'Connecting…'; color = '#33474A'; line = 'Connecting to the backend…'; }
      else if (e.engine === 'quantumrings' && e.ready) {
        pill = 'Quantum Rings SDK'; color = '#0A625F';
        line = 'QuantumRingsLib · backend ' + e.backend + (s.qMs !== null && s.qEngine === 'quantumrings' ? ' · last pull ' + s.qMs + ' ms' : '');
      } else if (e.engine === 'quantumrings') {
        pill = 'Quantum Rings unavailable'; color = '#8E1D16'; line = e.error + ' Pulls will fail rather than fake bits.';
      } else {
        pill = 'Mock engine'; color = '#7A5200';
        line = 'QUANTUM_MODE=mock: the OS’s crypto randomness stands in for Quantum Rings. Set QUANTUM_MODE=quantumrings in .env to run the real circuits.';
      }
    }
    text('src-pill', pill);
    $('src-pill').style.color = color;
    $('src-dot').style.background = color;
    text('src-line', line);
    $('src-line').style.color = color;
    text('src-note', srcNote);

    // closing band: replay result per source
    const cm = c.bitsB ? matchCount(c.bitsA, c.bitsB) : null;
    const qm = q.bitsB ? matchCount(q.bitsA, q.bitsB) : null;
    text('c-big', cm === null ? '—/64' : cm + '/64');
    $('c-big').style.color = cm === null ? '#B4C6C8' : '#F0A79B';
    text('q-big', qm === null ? '—/64' : qm + '/64');
    $('q-big').style.color = qm === null ? '#B4C6C8' : (isPole(q.theta) ? '#F0A79B' : '#8FD9B0');

    // ----- attack
    const ready = c.bitsA && q.bitsA;
    $('btn-attack').disabled = s.atkBusy || !ready;
    text('btn-attack', s.atkBusy ? 'Attacking…' : (s.atkC ? 'Attack again' : 'Attack both runs'));
    let atkStatus;
    if (s.atkErr) atkStatus = s.atkErr;
    else if (s.atkBusy) atkStatus = 'Brute-forcing both runs on the server…';
    else if (!c.bitsA && !q.bitsA) atkStatus = 'Spin once with the switch on Seeded PRNG and once on Quantum draw.';
    else if (!c.bitsA) atkStatus = 'Now flip the switch to Seeded PRNG and spin once.';
    else if (!q.bitsA) atkStatus = 'Now flip the switch to Quantum draw and spin once.';
    else if (!s.atkC) atkStatus = 'Ready. The attacker sees ' + fmt(Math.floor(c.bitsA.length / 2)) + ' PRNG bits and ' + fmt(Math.floor(q.bitsA.length / 2)) + ' quantum bits.';
    else if (s.atkQ && isPole(q.theta)) atkStatus = 'At θ = ' + q.theta + '° every qubit reads ' + (q.theta === 0 ? '0' : '1') + ', so anyone could predict it without a seed. Set θ to 90° and spin again.';
    else atkStatus = 'The seed gave the PRNG spin away. The qubits had no seed to find.';
    text('attack-status', atkStatus);
    renderAttack('c', s.atkC);
    renderAttack('q', s.atkQ);

    html.classList.toggle('qf-still', !s.motion);
  }

  function renderAttack(side, a) {
    const big = $('atk-' + side + '-big');
    if (!a) {
      text('atk-' + side + '-big', '—');
      big.style.color = '#B4C6C8';
      text('atk-' + side + '-detail', '');
      paintHits('atk' + side.toUpperCase(), null, '', '', '#1B2C2F');
      return;
    }
    text('atk-' + side + '-big', pct(a.accuracy) + ' · ' + fmt(a.correct) + '/' + fmt(a.hidden_bits));
    big.style.color = a.accuracy > 0.9 ? '#F0A79B' : '#8FD9B0';
    const secs = (a.elapsed_ms / 1000).toFixed(2) + ' s';
    text('atk-' + side + '-detail', a.seed !== null
      ? 'Tried ' + fmt(a.seeds_tried) + ' seeds in ' + secs + '. Seed ' + pad4(a.seed) + ' fits the first ' + fmt(a.known_bits) + ' bits, and it predicts every hidden one.'
      : 'Tried ' + fmt(a.seeds_tried) + ' seeds in ' + secs + '. None fits, so the attacker can only guess: a coin flip.');
    paintHits('atk' + side.toUpperCase(), a, '#F0A79B', '#3A4C4F', '#1B2C2F');
  }

  // ---------------------------------------------------------------- wire up
  function init() {
    buildParts();
    scene.els = {
      open: $('top'), crack: $('crack-scene'), turn: $('fix'),
      ch: ['top', 'crack', 'stakes', 'fix', 'demo', 'deployed'].map((id) => $(id))
    };

    $('btn-motion').addEventListener('click', () => set({ motion: !S.motion }));
    $('api-retry').addEventListener('click', connect);

    // the crack card
    let crackTimer = 0;
    $('crack-seed').addEventListener('input', (e) => {
      clearTimeout(crackTimer);
      const v = parseSeed(e.target.value);
      if (v === null) { crackToken++; set({ crackRuns: [], crackErr: 'Use a whole number from 0 to 9,999.' }); return; }
      crackTimer = setTimeout(() => pullThree(v), 250);
    });
    $('crack-random').addEventListener('click', () => {
      const v = Math.floor(Math.random() * 10000);
      $('crack-seed').value = String(v);
      pullThree(v);
    });
    bindDrag($('c-wrap'), 'reels');

    // the turn
    document.querySelectorAll('[data-go]').forEach((b) => b.addEventListener('click', () => goBeat(Number(b.dataset.go))));
    $('btn-tagain').addEventListener('click', () => turnBit(true));

    // the switch: click, or arrow keys like any radio group
    const opts = Array.from(document.querySelectorAll('.src-opt'));
    opts.forEach((b) => {
      b.addEventListener('click', () => setSource(b.dataset.src));
      b.addEventListener('keydown', (e) => {
        if (!['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(e.key)) return;
        e.preventDefault();
        const next = opts[(opts.indexOf(b) + 1) % opts.length];
        setSource(next.dataset.src);
        next.focus();
      });
    });

    // the machine
    document.querySelectorAll('.shots').forEach((b) => b.addEventListener('click', () => set({ shots: Number(b.dataset.shots) })));
    bindDrag($('orbit'), 'orbit');
    const lever = $('btn-lever');
    bindDrag(lever, 'lever');
    lever.addEventListener('pointerdown', (e) => e.stopPropagation());
    lever.addEventListener('click', () => { if (levHandled) { levHandled = false; return; } spin('clock'); });
    $('btn-reset-view').addEventListener('click', () => {
      orbit.rx = -6; orbit.ry = -18;
      document.documentElement.style.removeProperty('--d-rx');
      document.documentElement.style.removeProperty('--d-ry');
    });
    $('btn-spin').addEventListener('click', () => spin('clock'));
    $('btn-replay').addEventListener('click', () => spin('replay'));
    $('btn-typed').addEventListener('click', spinTyped);
    $('seed-in').addEventListener('input', (e) => set({ seedDraft: e.target.value, err: '' }));
    $('seed-in').addEventListener('keydown', (e) => { if (e.key === 'Enter') spinTyped(); });
    $('spin-time').addEventListener('input', (e) => set({ spinSec: Number(e.target.value) }));

    // the qubits
    $('theta').addEventListener('input', (e) => setTheta(Number(e.target.value)));
    document.querySelectorAll('.th').forEach((b) => b.addEventListener('click', () => setTheta(Number(b.dataset.theta))));
    bindDrag($('q-drag'), 'qubit');
    $('btn-attack').addEventListener('click', runAttack);

    // scroll scenes
    window.addEventListener('scroll', () => { if (!scene.raf) scene.raf = requestAnimationFrame(tick); }, { passive: true });
    window.addEventListener('resize', () => {
      const w = window.innerWidth, h = window.innerHeight;
      if (scene.scrollMode && w === scene.vw && Math.abs(h - scene.vh) < 140) return;
      setup();
    });
    window.addEventListener('pointermove', parallax, { passive: true });
    setup();
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(setup);

    $('api-url').textContent = API_CANDIDATES.filter(Boolean).join(' or ') || location.origin;
    render();
    connect();
  }

  async function connect() {
    if (!(await findApi())) { set({ apiOffline: true }); return; }
    set({ apiOffline: false });
    $('api-url').textContent = API || location.origin;
    loadEngine();
    loadState(S.theta);
    const seed = parseSeed($('crack-seed').value);
    if (seed !== null) pullThree(seed);
  }

  init();
})();
