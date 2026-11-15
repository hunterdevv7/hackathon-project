"""
Lucky Bits - two slot machines side by side: a red classical one and a
green quantum one. Same reels, same lever, very different randomness.

  * CLASSICAL (red): every spin is GET /classical-draw, 100 bits from
    Python's random.Random(seed), where the seed is the current Unix time in
    seconds. NEXT SPIN (bottom left) runs the same replay function on the
    clock and shows the number the next pull will land on, before you pull.
    That's the crack.
  * QUANTUM (green): every spin is GET /quantum-draw. There is no seed, so
    there is nothing to replay and NEXT SPIN stays "????". Until the quantum
    source is plugged in (rng_api.register_source("quantum", fn)), the API
    serves a stand-in from the operating system's entropy pool, and the
    machine's display says STAND-IN.
  * The 4 reels show the 100 bits as a number from 0000 to 9999. The strip
    under the display runs the randomness test (frequency + runs) on all 100
    bits. Both machines usually pass: a pseudo-random generator looks random,
    it just isn't secret.

Controls: pull a lever (drag the knob down, or just click it), or press a
SPIN button, which drops a coin in first. Space or Enter spins both
machines, 1 spins the classical one, 2 the quantum one. M (or clicking the
hint line at the bottom right) turns sound on or off.

The API is rng_api.py (start it with: python rng_api.py). Set LUCKY_BITS_API
to use one somewhere other than http://127.0.0.1:5000. If nothing answers,
the machines run the same code in-process and the bottom line says LOCAL MODE.

Needs nothing beyond the standard library, plus classical_rng.py.
Sound works on Windows only.
"""

import atexit
import http.client
import json
import math
import os
import random
import secrets
import shutil
import sys
import tempfile
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
import urllib.error
import urllib.request
import wave
from array import array
from functools import lru_cache

try:
    import winsound
except ImportError:  # not on Windows: run without sound
    winsound = None

try:  # the code the API runs: the predictor, and the fallback with no API
    import classical_rng as crng
except ImportError:
    crng = None


# --------------------------------------------------------------------------
# Layout, in design pixels. Everything is multiplied by the display scale.
# Each machine is drawn in a 620-wide slot, shifted right by its offset.
# --------------------------------------------------------------------------
W, H = 1200, 766
MACHINE_X = (0, 590)
N_DIGITS = 4
N_BITS = 100
API_URL = os.environ.get("LUCKY_BITS_API", "http://127.0.0.1:5000").rstrip("/")
API_TIMEOUT = 3.0
API_RETRY = 15.0    # seconds in local mode before trying the API again (Windows
                    # takes ~2 s to refuse a connection, too slow to pay every spin)

# Shared palette
BG = "#0b0f0c"
FLOOR = "#060908"
SHADOW = "#040605"
GOLD = "#e3b94c"
GOLD_DARK = "#8c6a1c"
GOLD_TEXT = "#ffd965"
WINDOW = "#070907"
REEL_BG = "#fbf5e4"
REEL_SHADE = "#77715f"
REEL_EDGE = "#5d584b"
INK = "#151515"
JACKPOT_INK = "#c8102e"
PAYLINE = "#ff3b30"
LED_BG = "#140c02"
AMBER = "#ffb22e"
AMBER_HOT = "#fff0c4"
AMBER_DIM = "#9a6415"
LED_ERR = "#ff6b4a"
LED_GOOD = "#7dffa8"
CHROME = "#b8c1c8"
CHROME_DARK = "#6f7a83"
CHROME_HI = "#eef3f6"
BULB_ON = "#ffe27a"
BULB_ON_EDGE = "#fff7d6"
BULB_OFF = "#4a3c12"
BULB_OFF_EDGE = "#2b2209"
BULB_RED = "#ff4d4d"
COIN = "#f2c94c"
COIN_BACK = "#d4a937"
COIN_EDGE = "#9a7316"
COIN_RING = "#c99b2a"
COIN_SHINE = "#fff4bd"
SLIT = "#111111"
STATUS_DIM = "#6f8f7a"

THEMES = {
    "classical": {  # red cabinet, gold button, black knob
        "title": "CLASSICAL",
        "body": "#b3202b", "body_edge": "#5e0a13", "plinth": "#4f0b13",
        "face": "#cf2d39", "face_hi": "#e5535e", "marquee": "#3f0b11",
        "title_shadow": "#2a0508", "bezel": "#3a0a10",
        "button": "#e8a420", "button_hover": "#f7bb3a", "button_edge": "#7a5208",
        "button_outline": "#ffd98a", "button_text": "#2b1700",
        "knob": "#26282b", "knob_dark": "#000000", "knob_hi": "#80868c",
        "tray": "#2b0609", "tray_line": "#4d1018", "ink": "#ffe2e2",
    },
    "quantum": {  # the original green cabinet, red button, red knob
        "title": "QUANTUM",
        "body": "#11803f", "body_edge": "#085227", "plinth": "#0a4a25",
        "face": "#16a052", "face_hi": "#22b964", "marquee": "#0a3a1f",
        "title_shadow": "#041a0c", "bezel": "#062a15",
        "button": "#d8232c", "button_hover": "#ee3740", "button_edge": "#7f0e14",
        "button_outline": "#ff6f75", "button_text": "#fff7e8",
        "knob": "#d8232c", "knob_dark": "#7f0e14", "knob_hi": "#ff7d84",
        "tray": "#04200f", "tray_line": "#0d3a20", "ink": "#d9f7e4",
    },
}

# Fonts, best first
DIGIT_FONTS = ("Rockwell", "Georgia", "Bahnschrift", "Helvetica")
TITLE_FONTS = ("Rockwell", "Arial Black", "Helvetica")
UI_FONTS = ("Bahnschrift SemiBold", "Bahnschrift", "Segoe UI", "Helvetica")
LED_FONTS = ("Consolas", "Courier New", "Courier")

# Reel motion
REEL_SPEED = 24.0   # digits per second at full spin
RAMP = 0.20         # seconds for a reel to reach full speed
DECEL = 0.90        # seconds each reel spends braking
FIRST_STOP = 0.75   # when the first reel starts braking

# Lever geometry
LEVER_PIVOT = (548, 330)
LEVER_LEN = 175
LEVER_MAX = math.radians(158)  # how far the arm swings when pulled
KNOB_R = 21

# Coin dropped in by the SPIN button
COIN_SLOT = (429, 558)      # centre of the slit
COIN_FROM = (548, 775)      # starts just below the bottom edge of the window
COIN_VIA = (508, 505)       # curve control point
COIN_R = 13
COIN_FLIGHT = 0.60          # seconds flying to the slot
COIN_INSERT = 0.22          # seconds sliding in


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------
@lru_cache(maxsize=None)
def _rgb(color):
    return int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)


def mix(a, b, t):
    """Blend colour a toward colour b by t (0..1)."""
    t = 0.0 if t < 0 else 1.0 if t > 1 else t
    ra, ga, ba = _rgb(a)
    rb, gb, bb = _rgb(b)
    return "#%02x%02x%02x" % (round(ra + (rb - ra) * t),
                              round(ga + (gb - ga) * t),
                              round(ba + (bb - ba) * t))


def ease_out_back(x, c1=1.0):
    """0 -> 1 with a small overshoot past 1 before settling."""
    c3 = c1 + 1
    u = x - 1
    return 1 + c3 * u ** 3 + c1 * u ** 2


def rounded_points(x0, y0, x1, y1, r):
    return (x0 + r, y0, x0 + r, y0, x1 - r, y0, x1 - r, y0, x1, y0,
            x1, y0 + r, x1, y0 + r, x1, y1 - r, x1, y1 - r, x1, y1,
            x1 - r, y1, x1 - r, y1, x0 + r, y1, x0 + r, y1, x0, y1,
            x0, y1 - r, x0, y1 - r, x0, y0 + r, x0, y0 + r, x0, y0)


def brake_times(n):
    """When each reel starts braking, left to right."""
    gap = max(0.18, min(0.45, 1.5 / max(n, 1)))
    return [FIRST_STOP + i * gap for i in range(n)]


def plan_reel(start, target, brake_at, speed=REEL_SPEED, faces=10):
    """Plan a spin that ends exactly on `target`.

    Picks a whole number of digits to travel that lands on the target digit,
    then the cruising speed that makes the trip end exactly on schedule, so
    reels always stop left to right at the planned moments.
    """
    span = brake_at - RAMP / 2 + DECEL / 4  # distance travelled per unit speed
    base = round(speed * span)
    delta = (target - start - base) % faces
    if delta > faces // 2:
        delta -= faces
    distance = base + delta
    return (start, distance, distance / span, brake_at)


def reel_position(plan, t):
    """Where a reel is, in digits, t seconds after the spin starts."""
    start, distance, v, brake_at = plan
    if t <= 0:
        return start
    if t < RAMP:                       # spinning up
        return start + v * t * t / (2 * RAMP)
    if t < brake_at:                   # cruising
        return start + v * (t - RAMP / 2)
    if t < brake_at + DECEL:           # braking, with a little bounce
        x = (t - brake_at) / DECEL
        return start + v * (brake_at - RAMP / 2) + v * DECEL / 4 * ease_out_back(x)
    return start + distance


def bits_to_number(bits, digits=N_DIGITS):
    """The machine's number: the 100 bits read as one binary number, mod 10**digits.

    Same bits, same number, so replaying a seed gives the same number. Every
    number is equally likely to within about 1 part in 10**26.
    """
    return int("".join(map(str, bits)), 2) % 10 ** digits


def fmt(number):
    return "—" if number is None else f"{number:0{N_DIGITS}d}"


def clock(seed):
    """HH:MM:SS for a seed that is a Unix time."""
    try:
        return time.strftime("%H:%M:%S", time.localtime(seed))
    except (OverflowError, OSError, ValueError, TypeError):
        return "?"


def os_entropy_bits(n=N_BITS):
    """Stand-in for the quantum source: bits from the OS entropy pool.
    No seed, so nothing can replay them, but they are not quantum."""
    value = secrets.randbits(n)
    return [(value >> i) & 1 for i in range(n)]


def standin_draw():
    return {"bits": os_entropy_bits(), "seed": None, "source": "quantum", "standin": True}


def error_text(exc):
    return str(exc) if isinstance(exc, ApiError) else f"{type(exc).__name__}: {exc}"


# --------------------------------------------------------------------------
# Talking to the API
# --------------------------------------------------------------------------
class ApiError(Exception):
    """The API (or the local fallback) refused a request; the message says why."""

    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


def need_crng():
    if crng is None:
        raise ApiError("API offline, and classical_rng.py is missing")
    return crng


class Job:
    """Runs fn(*args) in a background thread; the UI checks .done each frame."""

    def __init__(self, fn, *args):
        self.result = self.error = None
        self.done = False
        threading.Thread(target=self._run, args=(fn, args), daemon=True).start()

    def _run(self, fn, args):
        try:
            self.result = fn(*args)
        except Exception as exc:
            self.error = exc
        self.done = True


class RngClient:
    """Calls the API in rng_api.py. If nothing answers, it runs the same code
    in this process (and the stand-in for quantum), so the machines keep working."""

    def __init__(self, base_url):
        self.base = base_url
        self.mode = "checking"   # then "online" or "local"
        self.retry_at = 0.0      # while the API is down, skip it until this time
        # Straight to the API: a system proxy setting could swallow 127.0.0.1.
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def ping(self):
        """Is the API up? OPTIONS is answered by Flask without drawing anything.
        Always asks, even while the API is marked down."""
        try:
            self._http("OPTIONS", "/classical-draw")
        except ApiError:
            pass  # something answered
        except (OSError, http.client.HTTPException):
            self._went_down()
        return self.mode

    def draw(self, source):
        """A draw for one machine: {"bits", "seed", "standin"}."""
        if source == "classical":
            result = self._call("GET", "/classical-draw", None,
                                lambda: need_crng().classical_draw())
        else:
            try:
                result = self._call("GET", "/quantum-draw", None, standin_draw)
            except ApiError as exc:
                if exc.status != 404:
                    raise
                result = standin_draw()  # an API without /quantum-draw
        return self._check_draw(result, source)

    def stat_test_bits(self, bits):
        """{"pass", "score"} for a batch of bits (POST /stat-test)."""
        result = self._call("POST", "/stat-test", {"bits": bits},
                            lambda: need_crng().stat_test(bits))
        if not (isinstance(result, dict) and isinstance(result.get("pass"), bool)
                and isinstance(result.get("score"), (int, float))):
            raise ApiError("the API sent a stat test in an unexpected shape")
        return {"pass": result["pass"], "score": float(result["score"])}

    def _went_down(self):
        self.mode = "local"
        self.retry_at = time.monotonic() + API_RETRY

    def _call(self, method, path, body, local):
        """Call the API; if nothing is listening, run `local()` instead."""
        if time.monotonic() >= self.retry_at:
            try:
                return self._http(method, path, body)
            except (OSError, http.client.HTTPException):
                self._went_down()
        try:
            return local()
        except ValueError as exc:
            raise ApiError(str(exc)) from None

    def _http(self, method, path, body=None):
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(self.base + path, data=data, method=method)
        if data is not None:
            request.add_header("Content-Type", "application/json")
        try:
            with self._opener.open(request, timeout=API_TIMEOUT) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            with exc:
                raw = exc.read()
            self.mode = "online"
            raise ApiError(self._message(raw) or f"HTTP {exc.code}", exc.code) from None
        self.mode = "online"
        self.retry_at = 0.0
        if not raw:
            return None
        try:
            return json.loads(raw)
        except ValueError:
            raise ApiError("the API's reply wasn't JSON") from None

    @staticmethod
    def _message(raw):
        try:
            return json.loads(raw).get("error")
        except Exception:
            return None

    @staticmethod
    def _check_draw(result, source):
        try:
            bits = [int(b) for b in result["bits"]]
            seed = result.get("seed")
            ok = len(bits) == N_BITS and set(bits) <= {0, 1}
            if source == "classical":
                ok = ok and isinstance(seed, int) and not isinstance(seed, bool)
        except (TypeError, KeyError, ValueError, AttributeError):
            ok = False
        if not ok:
            raise ApiError(f"the API sent a {source} draw in an unexpected shape")
        return {"bits": bits, "seed": seed, "standin": bool(result.get("standin", False))}


# --------------------------------------------------------------------------
# Sound: tiny synthesized WAV files played with winsound
# --------------------------------------------------------------------------
class Sound:
    RATE = 22050

    def __init__(self):
        self.available = winsound is not None
        self.enabled = self.available
        self.files = {}
        self.building = set()
        self.dir = None
        if not self.available:
            return
        try:
            self.dir = tempfile.mkdtemp(prefix="lucky_bits_")
            atexit.register(self.close)
            self._save("lever", self._lever())
            self._save("coin", self._coin())
            self._save("jackpot", self._jackpot())
        except Exception:
            self.available = self.enabled = False

    # -- public -------------------------------------------------------------
    def prepare_spin(self, reels):
        """Build the spin soundtrack for this many reels in the background."""
        name = f"spin{reels}"
        if not self.available or name in self.files or name in self.building:
            return
        self.building.add(name)
        threading.Thread(target=self._build_spin, args=(reels,), daemon=True).start()

    def play(self, name):
        path = self.files.get(name)
        if not (self.enabled and path):
            return
        try:
            winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC
                               | winsound.SND_NODEFAULT)
        except RuntimeError:
            pass

    def stop(self):
        if self.available:
            try:
                winsound.PlaySound(None, 0)
            except RuntimeError:
                pass

    def toggle(self):
        if self.available:
            self.enabled = not self.enabled
            if not self.enabled:
                self.stop()

    def close(self):
        self.stop()
        if self.dir:
            shutil.rmtree(self.dir, ignore_errors=True)
            self.dir = None

    # -- synthesis ----------------------------------------------------------
    def _build_spin(self, reels):
        try:
            self._save(f"spin{reels}", self._spin(reels))
        except Exception:
            pass

    def _buffer(self, seconds):
        return [0.0] * int(seconds * self.RATE)

    def _click(self, buf, t, amp, tone, length, rng):
        rate = self.RATE
        i0, n = int(t * rate), int(length * rate)
        w = 2 * math.pi * tone / rate
        for k in range(min(n, len(buf) - i0)):
            env = (1 - k / n) ** 2
            buf[i0 + k] += amp * env * (0.6 * math.sin(w * k) + 0.4 * (rng.random() * 2 - 1))

    def _thunk(self, buf, t, amp, rng):
        rate = self.RATE
        i0, n = int(t * rate), int(0.11 * rate)
        for k in range(min(n, len(buf) - i0)):
            s = k / rate
            body = (math.sin(2 * math.pi * 90 * s) * math.exp(-s * 38)
                    + 0.5 * math.sin(2 * math.pi * 210 * s) * math.exp(-s * 60))
            snap = (rng.random() * 2 - 1) * math.exp(-s * 400) * 0.6
            buf[i0 + k] += amp * (body + snap)

    def _bell(self, buf, t, freq, amp, length):
        rate = self.RATE
        i0, n = int(t * rate), int(length * rate)
        w = 2 * math.pi * freq
        for k in range(min(n, len(buf) - i0)):
            s = k / rate
            env = math.exp(-s * 5.5) * min(1.0, s * 400)
            buf[i0 + k] += amp * env * (math.sin(w * s) + 0.35 * math.sin(w * 2.01 * s)
                                        + 0.12 * math.sin(w * 3.02 * s))

    def _lever(self):
        rng = random.Random(1)
        buf = self._buffer(0.3)
        t = 0.0
        for k in range(7):  # ratchet clicks as the arm comes down
            self._click(buf, t, 0.45 - k * 0.03, 1700, 0.006, rng)
            t += 0.034 - k * 0.002
        return buf

    def _coin(self):
        """A metallic clink, then the coin rattling down inside."""
        buf = self._buffer(0.4)
        rate = self.RATE
        for start, amp in ((0.0, 0.5), (0.07, 0.28), (0.12, 0.16), (0.155, 0.09)):
            i0 = int(start * rate)
            for freq in (2960, 4110, 5830):  # out-of-tune partials sound like metal
                w = 2 * math.pi * freq / rate
                for k in range(min(int(0.12 * rate), len(buf) - i0)):
                    buf[i0 + k] += amp / 3 * math.sin(w * k) * math.exp(-k / rate * 40)
        return buf

    def _spin(self, reels):
        rng = random.Random(7)
        brakes = brake_times(reels)
        end = brakes[-1] + DECEL
        buf = self._buffer(end + 0.9)
        self._thunk(buf, 0.0, 0.55, rng)  # the lever hitting the bottom
        step = 0.0005
        for brake_at in brakes:
            plan = plan_reel(0, 0, brake_at)
            last, t = 0, 0.0
            while t < brake_at + DECEL:  # a tick each time a digit passes
                passed = math.floor(reel_position(plan, t))
                if passed > last:
                    self._click(buf, t, 0.10 + rng.random() * 0.04,
                                2600 + rng.random() * 600, 0.004, rng)
                    last = passed
                t += step
            self._thunk(buf, brake_at + DECEL * 0.55, 0.65, rng)  # reel locks
        self._bell(buf, end + 0.05, 987.8, 0.28, 0.7)
        self._bell(buf, end + 0.17, 1318.5, 0.28, 0.7)
        return buf

    def _jackpot(self):
        buf = self._buffer(1.8)
        for i, freq in enumerate((523.25, 659.25, 783.99, 1046.5, 1318.5, 1568.0)):
            self._bell(buf, i * 0.085, freq, 0.22, 0.6)
        for freq in (1046.5, 1318.5, 1568.0):
            self._bell(buf, 0.6, freq, 0.2, 1.1)
        return buf

    def _save(self, name, buf):
        peak = max(1e-9, max(abs(s) for s in buf))
        gain = min(1.0, 0.9 / peak) * 32767
        data = array("h", (int(s * gain) for s in buf))
        if sys.byteorder == "big":
            data.byteswap()
        path = os.path.join(self.dir, name + ".wav")
        with wave.open(path, "wb") as out:
            out.setnchannels(1)
            out.setsampwidth(2)
            out.setframerate(self.RATE)
            out.writeframes(data.tobytes())
        self.files[name] = path


# --------------------------------------------------------------------------
# One reel: its own little canvas, so digits are clipped to the window
# --------------------------------------------------------------------------
class Reel:
    def __init__(self, parent, x, y, w, h, font, cell, start_digit):
        self.w, self.h, self.cell = w, h, cell
        self.cy = h / 2
        self.canvas = tk.Canvas(parent, width=w, height=h, bg=REEL_BG,
                                highlightthickness=0, bd=0)
        parent.create_window(x, y, window=self.canvas, anchor="nw")

        # Shade toward the top and bottom so the strip reads as a drum.
        half = h / 2
        self.shade = []
        for yy in range(int(h) + 1):
            color = mix(REEL_BG, REEL_SHADE, min(1.0, abs(yy - self.cy) / half) ** 2.4)
            self.shade.append(color)
            self.canvas.create_line(0, yy, w, yy, fill=color)
        self.canvas.create_line(0, 0, 0, h, fill=REEL_EDGE)
        self.canvas.create_line(w - 1, 0, w - 1, h, fill=REEL_EDGE)

        # Line up the digit's visual centre with the pay line.
        size = -font.cget("size")
        self.nudge = 0.36 * size - (font.metrics("ascent") - font.metrics("descent")) / 2
        self.items = [self.canvas.create_text(w / 2, self.cy, text="", font=font)
                      for _ in range(5)]

        self.rest = start_digit  # whole-digit position while stopped
        self.pos = float(start_digit)
        self.plan = None
        self.speed = 0.0
        self.ink = INK
        self.render()

    def start(self, target, brake_at):
        self.ink = INK
        self.plan = plan_reel(self.rest, target, brake_at)

    def update(self, t, dt):
        """Advance to time t. Returns True while still spinning."""
        p = reel_position(self.plan, t)
        self.speed = abs(p - self.pos) / dt
        self.pos = p
        if t >= self.plan[3] + DECEL:
            self.rest = self.plan[0] + self.plan[1]
            self.pos = float(self.rest)
            self.plan = None
            self.speed = 0.0
        self.render()
        return self.plan is not None

    def render(self):
        base = math.floor(self.pos)
        frac = self.pos - base
        blur = min(0.55, self.speed / 45.0)  # fast digits look faded
        half = self.h / 2
        for j, item in zip((-2, -1, 0, 1, 2), self.items):
            y = self.cy - (j - frac) * self.cell
            dist = min(1.0, abs(y - self.cy) / half)
            behind = self.shade[int(min(max(y, 0), self.h))]
            color = mix(self.ink, behind, min(0.92, blur + 0.9 * dist ** 1.7))
            self.canvas.coords(item, self.w / 2, y + self.nudge)
            self.canvas.itemconfigure(item, text=str((base + j) % 10), fill=color)


# --------------------------------------------------------------------------
# One machine, drawn on the shared canvas at its own x offset
# --------------------------------------------------------------------------
class Machine:
    def __init__(self, app, index, source):
        self.app = app
        self.cv = app.cv
        self.k = app.k
        self.index = index
        self.source = source          # "classical" or "quantum"
        self.ox = MACHINE_X[index]
        self.t = THEMES[source]
        self.reels = []
        self.history = []
        self.coins = []
        self.result = None            # the last finished spin
        self.pending = None           # the spin the reels are heading to
        self.spin_job = None          # the API call for the spin on its way
        self.test_job = None          # the stat test for the spin in progress
        self.stat = None              # its result, shown once the reels stop
        self.spinning = False
        self.spin_start = 0.0
        self.jackpot = False
        self.pred_seed = None         # classical only: the predictor's last seed...
        self.pred_number = None       # ...and the number it gives
        self.called_number = None     # what NEXT SPIN said when the lever was pulled
        self.called_seed = None
        self.called = False
        self.called_until = 0.0
        self.lever_a = 0.0            # 0 = up, 1 = pulled all the way down
        self.drawn_a = None
        self.lever_mode = "idle"
        self.lever_t0 = 0.0
        self.lever_from = 0.0
        self.lever_dur = 0.3
        self.drag = None
        self.button_down = False
        self.coin = None              # the coin animation in progress, if any
        self.slot_flash = None        # when the slot last lit up
        self.light_mode = "idle"
        self.celebrate_until = 0.0
        self.error_text = ""
        self.error_until = 0.0
        self.led_state = None
        self.next_state = None
        self.strip_state = None

        self._draw_cabinet()
        self._draw_marquee()
        self._draw_reel_window()
        self._draw_display()
        self._draw_strip()
        self._draw_spin_button()
        self._draw_history()
        self._draw_tray()
        self._draw_lever()
        self._build_reels()
        self.update_captions()
        self._bind()

    # -- coordinates --------------------------------------------------------
    def p(self, *xy):
        """Design (x, y, x, y, ...) to canvas pixels, shifted onto this machine."""
        return [(v + (self.ox if i % 2 == 0 else 0)) * self.k for i, v in enumerate(xy)]

    def pr(self, *xy):
        """Like p(), in whole pixels: Tk leaves stray pixels behind when items
        with fractional coordinates move every frame."""
        return [round(v) for v in self.p(*xy)]

    def z(self, v):
        return v * self.k

    def rr(self, x0, y0, x1, y1, r, **kw):
        if "width" in kw:
            kw["width"] = self.z(kw["width"])
        return self.cv.create_polygon(self.p(*rounded_points(x0, y0, x1, y1, r)),
                                      smooth=True, **kw)

    # -- static artwork -----------------------------------------------------
    def _draw_cabinet(self):
        cv, t = self.cv, self.t
        cv.create_oval(self.p(30, 704, 600, 738), fill=FLOOR, outline="")
        self.rr(62, 684, 488, 716, 10, fill=t["plinth"], outline=t["body_edge"], width=2)
        self.rr(58, 80, 508, 708, 30, fill=SHADOW, outline="")
        self.rr(50, 70, 500, 700, 30, fill=t["body"], outline=t["body_edge"], width=4)
        self.rr(66, 132, 484, 686, 22, fill=t["face"], outline=GOLD, width=2)
        self.rr(73, 140, 81, 678, 4, fill=t["face_hi"], outline="")  # sheen
        # coin slot, beside the SPIN button
        self.rr(418, 536, 440, 580, 6, fill=CHROME_DARK, outline="")
        self.slot_plate = self.rr(420, 538, 438, 578, 5, fill=CHROME, outline="")
        cv.create_rectangle(self.p(427, 544, 431, 572), fill=SLIT, outline="")

    def _draw_marquee(self):
        cv, t = self.cv, self.t
        self.rr(76, 14, 474, 122, 28, fill=GOLD_DARK, outline="")
        self.rr(80, 18, 470, 118, 26, fill=GOLD, outline="")
        self.rr(88, 26, 462, 110, 20, fill=t["marquee"], outline=GOLD_DARK, width=2)
        f = self.app.f_title
        cv.create_text(self.p(277, 71), text=t["title"], font=f, fill=t["title_shadow"])
        cv.create_text(self.p(275, 68), text=t["title"], font=f, fill=GOLD_TEXT)

        # Bulbs, listed in order around the sign so the chase runs in a loop.
        xs = [104 + i * (446 - 104) / 15 for i in range(16)]
        spots = ([(x, 37) for x in xs] + [(452, 58), (452, 78)]
                 + [(x, 99) for x in reversed(xs)] + [(98, 78), (98, 58)])
        self.bulbs = []
        for x, y in spots:
            glow = cv.create_oval(self.p(x - 7, y - 7, x + 7, y + 7), fill=t["marquee"],
                                  outline="")
            bulb = cv.create_oval(self.p(x - 4.5, y - 4.5, x + 4.5, y + 4.5),
                                  fill=BULB_OFF, outline=BULB_OFF_EDGE)
            self.bulbs.append((glow, bulb))
        self.bulb_state = [None] * len(self.bulbs)

    def _draw_reel_window(self):
        self.rr(72, 142, 478, 343, 18, fill=GOLD_DARK, outline="")
        self.rr(75, 145, 475, 340, 16, fill=GOLD, outline="")
        self.rr(84, 154, 466, 331, 10, fill=WINDOW, outline="#000000")
        cy = 242.5
        self.cv.create_polygon(self.p(87, cy - 8, 96, cy, 87, cy + 8), fill=PAYLINE, outline="")
        self.cv.create_polygon(self.p(463, cy - 8, 454, cy, 463, cy + 8), fill=PAYLINE, outline="")

    def _draw_display(self):
        cv, a = self.cv, self.app
        self.rr(95, 356, 455, 452, 14, fill=self.t["bezel"], outline=GOLD_DARK, width=2)
        self.rr(104, 365, 446, 443, 8, fill=LED_BG, outline="#000000")
        self.led_main = cv.create_text(self.p(275, 398), text="", font=a.f_led_msg, fill=AMBER)
        self.led_caption = cv.create_text(self.p(275, 431), text="", font=a.f_led_small,
                                          fill=AMBER_DIM)

    def _draw_strip(self):
        """The randomness test for the last spin, under the display."""
        cv, a = self.cv, self.app
        self.rr(95, 462, 455, 518, 10, fill=LED_BG, outline=GOLD_DARK, width=1.5)
        cv.create_text(self.p(112, 480), text="RANDOMNESS TEST", anchor="w",
                       font=a.f_label, fill=GOLD_TEXT)
        cv.create_text(self.p(112, 501), text="frequency + runs on all 100 bits", anchor="w",
                       font=a.f_tiny, fill=AMBER_DIM)
        self.strip_verdict = cv.create_text(self.p(440, 479), text="", anchor="e",
                                            font=a.f_led_mid, fill=AMBER_DIM)
        self.strip_score = cv.create_text(self.p(440, 502), text="", anchor="e",
                                          font=a.f_led_small, fill=AMBER_DIM)

    def _draw_spin_button(self):
        t, tag = self.t, f"spin{self.index}"
        face = (tag, f"face{self.index}")
        self.rr(177, 534, 373, 586, 26, fill=t["button_edge"], outline="", tags=(tag,))
        self.button_face = self.rr(177, 530, 373, 580, 25, fill=t["button"],
                                   outline=t["button_outline"], width=1.5, tags=face)
        self.cv.create_text(self.p(275, 555), text="SPIN", font=self.app.f_button,
                            fill=t["button_text"], tags=face)

    def _draw_history(self):
        cv, a = self.cv, self.app
        # left: what the next spin will be, if it can be known
        self.next_label = cv.create_text(self.p(146, 602), text="NEXT SPIN",
                                         font=a.f_label, fill=GOLD_TEXT)
        self.rr(86, 611, 206, 645, 7, fill=LED_BG, outline=GOLD_DARK, width=1.5)
        self.next_text = cv.create_text(self.p(146, 623), text="", font=a.f_led_mid,
                                        fill=AMBER)
        self.next_note = cv.create_text(self.p(146, 638.5), text="", font=a.f_led_tiny,
                                        fill=AMBER_DIM)
        cv.create_line(self.p(220, 598, 220, 642), fill=self.t["body_edge"], width=self.z(2))
        # right: the last spins, newest first
        cv.create_text(self.p(352, 602), text="LAST SPINS", font=a.f_label, fill=GOLD_TEXT)
        self.history_text = cv.create_text(self.p(352, 626), text="—", font=a.f_history,
                                           fill=self.t["ink"])

    def _draw_tray(self):
        self.rr(120, 650, 430, 684, 12, fill=CHROME_DARK, outline="")
        self.rr(123, 650, 427, 680, 10, fill=CHROME, outline="")
        self.rr(132, 655, 418, 676, 8, fill=self.t["tray"], outline="")
        self.cv.create_line(self.p(138, 659, 412, 659), fill=self.t["tray_line"], width=self.z(2))

    def _draw_lever(self):
        cv, t = self.cv, self.t
        px, py = LEVER_PIVOT
        # bracket bolted to the cabinet
        self.rr(492, 300, 536, 360, 10, fill=CHROME_DARK, outline="")
        self.rr(492, 302, 533, 356, 9, fill=CHROME, outline="")
        cv.create_line(self.p(498, 310, 527, 310), fill=CHROME_HI, width=self.z(2))
        # hub the arm swings on
        cv.create_oval(self.p(px - 26, py - 26, px + 26, py + 26), fill=CHROME_DARK, outline="")
        cv.create_oval(self.p(px - 23, py - 23, px + 23, py + 23), fill=CHROME, outline="")
        cv.create_oval(self.p(px - 15, py - 18, px + 5, py - 4), fill=CHROME_HI, outline="")
        # arm and knob, moved every frame
        tags = (f"lever{self.index}",)
        self.rod = cv.create_line(0, 0, 0, 0, fill=CHROME_DARK, capstyle="round", tags=tags)
        self.rod_mid = cv.create_line(0, 0, 0, 0, fill=CHROME, capstyle="round", tags=tags)
        self.rod_hi = cv.create_line(0, 0, 0, 0, fill=CHROME_HI, capstyle="round", tags=tags)
        cv.create_oval(self.p(px - 9, py - 9, px + 9, py + 9), fill=CHROME_DARK,
                       outline=CHROME_HI, width=self.z(1.5))
        self.knob = cv.create_oval(0, 0, 0, 0, fill=t["knob"], outline=t["knob_dark"],
                                   width=max(1, round(self.z(2))), tags=tags)
        self.knob_hi = cv.create_oval(0, 0, 0, 0, fill=t["knob_hi"], outline="", tags=tags)
        self.knob_spec = cv.create_oval(0, 0, 0, 0, fill="#ffffff", outline="", tags=tags)
        self._render_lever()

    def _build_reels(self):
        n, gap = N_DIGITS, 8
        left, right, top, bottom = 98, 452, 162, 323
        avail = right - left
        w = min(104, (avail - gap * (n - 1)) / n)
        x = left + (avail - (w * n + gap * (n - 1))) / 2
        font_px = min(96, w * 1.12)
        font = self.app.reel_font(font_px)
        for i in range(n):
            rx, ry = self.p(x + i * (w + gap), top)
            self.reels.append(Reel(self.cv, rx, ry, self.z(w), self.z(bottom - top),
                                   font, self.z(font_px), 7))

    # -- input --------------------------------------------------------------
    def _bind(self):
        cv = self.cv
        lever, spin = f"lever{self.index}", f"spin{self.index}"
        cv.tag_bind(lever, "<ButtonPress-1>", self._on_lever_press)
        cv.tag_bind(lever, "<Enter>", lambda e: cv.configure(cursor="hand2"))
        cv.tag_bind(lever, "<Leave>", lambda e: self.drag or cv.configure(cursor=""))
        cv.tag_bind(spin, "<Enter>", lambda e: self._hover_button(True))
        cv.tag_bind(spin, "<Leave>", lambda e: self._hover_button(False))
        cv.tag_bind(spin, "<ButtonPress-1>", self._on_button_press)

    def _hover_button(self, inside):
        self.cv.itemconfigure(self.button_face,
                              fill=self.t["button_hover"] if inside else self.t["button"])
        self.cv.configure(cursor="hand2" if inside else "")

    def _on_button_press(self, _):
        self.button_down = True
        self.cv.move(f"face{self.index}", 0, self.z(3))

    def _on_lever_press(self, event):
        if self.busy() or self.lever_mode != "idle":
            return
        knob_y = LEVER_PIVOT[1] - LEVER_LEN * math.cos(self.lever_a * LEVER_MAX)
        self.drag = {"y0": event.y, "offset": self.z(knob_y) - event.y, "moved": False}
        self.lever_mode = "drag"

    def on_drag(self, event):
        if not self.drag:
            return
        if abs(event.y - self.drag["y0"]) > self.z(4):
            self.drag["moved"] = True
        y = (event.y + self.drag["offset"]) / self.k
        c = max(-1.0, min(1.0, (LEVER_PIVOT[1] - y) / LEVER_LEN))
        self.lever_a = max(0.0, min(1.0, math.acos(c) / LEVER_MAX))
        self._render_lever()

    def on_release(self, _):
        if self.button_down:
            self.button_down = False
            self.cv.move(f"face{self.index}", 0, -self.z(3))
            if f"spin{self.index}" in self.cv.gettags("current"):
                self.insert_coin()
        if not self.drag:
            return
        moved = self.drag["moved"]
        self.drag = None
        self.cv.configure(cursor="")
        # A click, or a drag past halfway, pulls the lever the rest of the way.
        if (not moved or self.lever_a >= 0.5) and self.pull():
            return
        self._spring_back(0.45)

    # -- the crack: predicting the classical machine ------------------------
    def _predict(self, seed):
        """The number a classical spin seeded with `seed` lands on, from the
        same replay function the API uses. Recomputed once a second."""
        if crng is None:
            return None
        if seed != self.pred_seed:
            self.pred_seed = seed
            self.pred_number = bits_to_number(crng.replay(seed)["bits"])
        return self.pred_number

    # -- spinning -----------------------------------------------------------
    def busy(self):
        return bool(self.spinning or self.coin or self.spin_job
                    or self.lever_mode not in ("idle", "drag"))

    def pull(self):
        """Pull the lever and call the API. Returns True if a spin is on its way."""
        if self.busy():
            return False
        if self.source == "classical":  # NEXT SPIN's call, frozen as the lever goes
            self.called_seed = int(time.time())
            self.called_number = self._predict(self.called_seed)
        self.spin_job = Job(self.app.api.draw, self.source)
        self.lever_mode = "down"
        self.lever_t0 = time.perf_counter()
        self.lever_from = self.lever_a
        self.lever_dur = 0.06 + 0.22 * (1 - self.lever_a)
        self.app.sound.play("lever")
        return True

    def insert_coin(self):
        """Fly a coin into the slot, then pull the lever."""
        if self.busy() or self.lever_mode != "idle":
            return
        cv = self.cv
        self.coin = {
            "t0": time.perf_counter(),
            "dropped": False,
            "body": cv.create_oval(0, 0, 0, 0, fill=COIN, outline=COIN_EDGE,
                                   width=max(1, round(self.z(2)))),
            "ring": cv.create_oval(0, 0, 0, 0, fill="", outline=COIN_RING,
                                   width=max(1, round(self.z(1.5)))),
            "shine": cv.create_oval(0, 0, 0, 0, fill=COIN_SHINE, outline=""),
        }
        self._update_coin(self.coin["t0"])

    def _update_coin(self, now):
        coin = self.coin
        if coin is None:
            return
        t = now - coin["t0"]
        sx, sy = COIN_SLOT
        if t < COIN_FLIGHT:
            # Curve in toward the slot, slowing down, spinning as it goes,
            # and ending edge-on so it lines up with the slit.
            e = 1 - (1 - t / COIN_FLIGHT) ** 3
            u = 1 - e
            cx = u * u * COIN_FROM[0] + 2 * u * e * COIN_VIA[0] + e * e * sx
            cy = u * u * COIN_FROM[1] + 2 * u * e * COIN_VIA[1] + e * e * sy
            face = math.cos(4.5 * math.pi * e)  # 1 = facing you, 0 = edge-on
            r = COIN_R * (1.35 - 0.35 * e)      # shrinks as it moves away from you
            sink = 0.0
        else:
            if not coin["dropped"]:
                coin["dropped"] = True
                self.app.sound.play("coin")
                self.slot_flash = now
            sink = min(1.0, (t - COIN_FLIGHT) / COIN_INSERT)
            if sink >= 1:
                for key in ("body", "ring", "shine"):
                    self.cv.delete(coin[key])
                self.coin = None
                self.pull()
                return
            cx, cy, face = sx, sy, 0.0
            r = COIN_R * (1 - 0.3 * sink)       # pushed in, it fades into the slit

        squash = max(0.15, abs(face))
        fill = mix(COIN if face >= 0 else COIN_BACK, SLIT, sink)
        cv, pr = self.cv, self.pr
        cv.coords(coin["body"], *pr(cx - r * squash, cy - r, cx + r * squash, cy + r))
        cv.itemconfigure(coin["body"], fill=fill, outline=mix(COIN_EDGE, SLIT, sink))
        if squash > 0.3:
            ring = r * 0.72
            cv.coords(coin["ring"], *pr(cx - ring * squash, cy - ring, cx + ring * squash, cy + ring))
            cv.itemconfigure(coin["ring"], state="normal")
        else:
            cv.itemconfigure(coin["ring"], state="hidden")
        if face > 0.4:
            cv.coords(coin["shine"], *pr(cx - r * 0.5 * squash, cy - r * 0.58,
                                         cx - r * 0.1 * squash, cy - r * 0.22))
            cv.itemconfigure(coin["shine"], state="normal")
        else:
            cv.itemconfigure(coin["shine"], state="hidden")

    def _update_slot_flash(self, now):
        if self.slot_flash is None:
            return
        glow = 1 - (now - self.slot_flash) / 0.5
        if glow <= 0:
            self.slot_flash = None
            glow = 0
        self.cv.itemconfigure(self.slot_plate, fill=mix(CHROME, BULB_ON, glow))

    def _land_spin_job(self):
        """The API answered while the lever is held down: spin, or say why not."""
        job, self.spin_job = self.spin_job, None
        if job.error is None:
            self._start_spin(job.result)
            return
        self.called_number = None
        message = error_text(job.error)
        self._show_error(message.split(":")[0].split(",")[0].upper()[:22])

    def _start_spin(self, draw):
        number = bits_to_number(draw["bits"])
        self.pending = dict(draw, number=number, digits=fmt(number))
        for reel, digit, brake_at in zip(self.reels, self.pending["digits"],
                                         brake_times(N_DIGITS)):
            reel.start(int(digit), brake_at)
        self.spin_start = time.perf_counter()
        self.spinning = True
        self.jackpot = False
        self.light_mode = "chase"
        self.stat = "pending"
        self.test_job = Job(self.app.api.stat_test_bits, draw["bits"])
        self.app.sound.play(f"spin{N_DIGITS}")

    def _finish_spin(self, now):
        self.spinning = False
        self.result = self.pending
        digits = self.result["digits"]
        self.jackpot = len(set(digits)) == 1
        for reel in self.reels:
            reel.ink = JACKPOT_INK if self.jackpot else INK
            reel.render()
        self.history.insert(0, digits)
        del self.history[12:]
        self._update_history()
        if self.source == "classical" and self.called_number is not None:
            self.called = self.called_number == self.result["number"]
            self.called_until = now + 1.6
        self.update_captions()
        self.light_mode = "celebrate"
        self.celebrate_until = now + (3.0 if self.jackpot else 1.1)
        if self.jackpot:
            self.app.sound.play("jackpot")
            self._drop_coins()

    def _drop_coins(self, count=12):
        for _ in range(count):
            x, y = random.uniform(144, 406), random.uniform(661, 670)
            self.coins.append(self.cv.create_oval(self.p(x - 9, y - 4, x + 9, y + 4),
                                                  fill=COIN, outline=COIN_EDGE,
                                                  width=self.z(1)))
        while len(self.coins) > 48:
            self.cv.delete(self.coins.pop(0))

    # -- per-frame updates --------------------------------------------------
    def update(self, now, dt):
        self._update_coin(now)
        self._update_slot_flash(now)
        self._update_lever(now)
        if self.spinning:
            t = now - self.spin_start
            still = [reel.update(t, dt) for reel in self.reels if reel.plan is not None]
            if not any(still):
                self._finish_spin(now)
        # The test result waits for the reels to stop, then shows.
        if self.test_job is not None and self.test_job.done and not self.spinning:
            job, self.test_job = self.test_job, None
            self.stat = job.result if job.error is None else {"error": error_text(job.error)}
        self._update_strip()
        self._update_lights(now)
        self._update_display(now)
        self._update_prediction(now)

    def _spring_back(self, duration):
        self.lever_mode = "up"
        self.lever_t0 = time.perf_counter()
        self.lever_from = self.lever_a
        self.lever_dur = duration

    def _update_lever(self, now):
        mode = self.lever_mode
        if mode == "down":
            x = min(1.0, (now - self.lever_t0) / self.lever_dur)
            self.lever_a = self.lever_from + (1 - self.lever_from) * x * x
            if x >= 1:
                self.lever_mode = "hold"
                self.lever_t0 = now
        elif mode == "hold":  # stays down until the API has answered
            if self.spin_job is not None and self.spin_job.done:
                self._land_spin_job()
            if self.spin_job is None and now - self.lever_t0 >= 0.12:
                self._spring_back(0.6)
        elif mode == "up":
            x = min(1.0, (now - self.lever_t0) / self.lever_dur)
            self.lever_a = self.lever_from * (1 - ease_out_back(x, 1.7))
            if x >= 1:
                self.lever_a = 0.0
                self.lever_mode = "idle"
        self._render_lever()

    def _render_lever(self):
        a = self.lever_a
        if a == self.drawn_a:
            return
        self.drawn_a = a
        cv, pr = self.cv, self.pr

        def width(v):
            return max(1, round(v * self.k))

        px, py = LEVER_PIVOT
        theta = a * LEVER_MAX
        ky = py - LEVER_LEN * math.cos(theta)
        near = math.sin(theta)            # > 0 while the knob swings toward you
        r = KNOB_R * (1 + 0.3 * near)
        w = 1 + 0.25 * near
        cv.coords(self.rod, *pr(px, py, px, ky))
        cv.itemconfigure(self.rod, width=width(13 * w))
        cv.coords(self.rod_mid, *pr(px, py, px, ky))
        cv.itemconfigure(self.rod_mid, width=width(9 * w))
        cv.coords(self.rod_hi, *pr(px - 2 * w, py, px - 2 * w, ky))
        cv.itemconfigure(self.rod_hi, width=width(3 * w))
        cv.coords(self.knob, *pr(px - r, ky - r, px + r, ky + r))
        cv.coords(self.knob_hi, *pr(px - r * 0.62, ky - r * 0.66, px - r * 0.02, ky - r * 0.12))
        cv.coords(self.knob_spec, *pr(px - r * 0.45, ky - r * 0.5, px - r * 0.22, ky - r * 0.28))

    def _update_lights(self, now):
        if self.light_mode == "celebrate" and now >= self.celebrate_until:
            self.light_mode = "idle"
        mode = self.light_mode
        marquee = self.t["marquee"]
        for i, (glow, bulb) in enumerate(self.bulbs):
            color = BULB_ON
            if mode == "chase":
                on = (i - int(now * 18)) % 5 in (0, 1)
            elif mode == "celebrate":
                flip = int(now * 9) % 2
                if self.jackpot:
                    on = (i + flip) % 2 == 0
                    color = BULB_RED if (i // 2) % 2 else BULB_ON
                else:
                    on = flip == 0
            else:
                on = (i + int(now * 1.4)) % 2 == 0
            state = (on, color)
            if state == self.bulb_state[i]:
                continue
            self.bulb_state[i] = state
            if on:
                self.cv.itemconfigure(bulb, fill=color, outline=BULB_ON_EDGE)
                self.cv.itemconfigure(glow, fill=mix(marquee, color, 0.35))
            else:
                self.cv.itemconfigure(bulb, fill=BULB_OFF, outline=BULB_OFF_EDGE)
                self.cv.itemconfigure(glow, fill=marquee)

    def _show_error(self, text):
        self.error_text = text
        self.error_until = time.perf_counter() + 2.2

    def _update_display(self, now):
        a = self.app
        if self.spinning:
            dots = int((now - self.spin_start) * 4) % 4
            self._led("SPINNING" + "." * dots + " " * (3 - dots), a.f_led_msg, AMBER)
        elif self.spin_job is not None:
            dots = int(now * 4) % 4
            self._led("CALLING API" + "." * dots + " " * (3 - dots), a.f_led_msg, AMBER)
        elif now < self.error_until:
            self._led(self.error_text, a.f_led_msg, LED_ERR)
        elif self.result is not None:
            text, font, color = self.result["digits"], a.f_led_big, AMBER
            if now < self.celebrate_until:
                color = AMBER_HOT if int(now * 8) % 2 == 0 else AMBER
                if self.jackpot and int(now * 2.5) % 2 == 0:
                    text, font = "JACKPOT!", a.f_led_msg
            self._led(text, font, color)
        else:
            self._led("PULL THE LEVER", a.f_led_msg, AMBER)

    def _led(self, text, font, color):
        state = (text, str(font), color)
        if state != self.led_state:
            self.led_state = state
            self.cv.itemconfigure(self.led_main, text=text, font=font, fill=color)

    def _update_strip(self):
        s = self.stat
        if s is None:
            state = ("—", "", AMBER_DIM)
        elif s == "pending":
            state = ("…", "testing", AMBER_DIM)
        elif "error" in s:
            state = ("NO RESULT", s["error"].split(":")[0][:24], AMBER_DIM)
        else:
            state = ("PASS" if s["pass"] else "FAIL", f"score {s['score']:.4f}",
                     LED_GOOD if s["pass"] else LED_ERR)
        if state != self.strip_state:
            self.strip_state = state
            verdict, score, color = state
            self.cv.itemconfigure(self.strip_verdict, text=verdict, fill=color)
            self.cv.itemconfigure(self.strip_score, text=score, fill=color)

    def _update_prediction(self, now):
        in_flight = self.spin_job is not None or self.spinning
        if self.source == "quantum":
            state = ("THIS SPIN" if in_flight else "NEXT SPIN", "????", AMBER, "NO SEED TO REPLAY")
        elif crng is None:
            state = ("NEXT SPIN", "—", AMBER_DIM, "NO REPLAY CODE")
        elif in_flight and self.called_number is not None:
            state = ("PREDICTED", fmt(self.called_number), AMBER, f"SEED {self.called_seed}")
        elif now < self.called_until:  # was the prediction right?
            if self.called:
                state = ("CALLED IT ✓", fmt(self.called_number), LED_GOOD, "SAW IT COMING")
            else:
                state = ("MISSED ✗", fmt(self.called_number), LED_ERR, "CLOCK TICKED")
        else:
            seed = int(time.time())
            state = ("NEXT SPIN", fmt(self._predict(seed)), AMBER, f"SEED {seed}")
        if state != self.next_state:
            self.next_state = state
            label, text, color, note = state
            self.cv.itemconfigure(self.next_label, text=label)
            self.cv.itemconfigure(self.next_text, text=text, fill=color)
            self.cv.itemconfigure(self.next_note, text=note)

    def update_captions(self):
        r = self.result
        if self.source == "classical":
            caption = "SEED = THE CLOCK" if r is None else f"SEED {r['seed']} = {clock(r['seed'])}"
        elif r is None:
            caption = "NO SEED, NOTHING TO REPLAY"
        elif r["standin"]:
            caption = "STAND-IN: OS ENTROPY, NOT QUANTUM"
        else:
            caption = "QUANTUM SOURCE · NO SEED"
        self.cv.itemconfigure(self.led_caption, text=caption)

    def _update_history(self):
        shown = []
        for digits in self.history:
            trial = "   ".join(shown + [digits])
            if self.app.f_history.measure(trial) > self.z(236):
                break
            shown.append(digits)
        self.cv.itemconfigure(self.history_text, text="   ".join(shown) or "—")


# --------------------------------------------------------------------------
# The window: both machines, the API, sound, keys and the frame loop
# --------------------------------------------------------------------------
class App:
    def __init__(self, root, scale):
        self.root = root
        self.k = scale
        root.title("Lucky Bits: classical vs quantum")
        root.configure(bg=BG)
        root.resizable(False, False)
        root.protocol("WM_DELETE_WINDOW", self.close)

        self.cv = tk.Canvas(root, width=W * scale, height=H * scale, bg=BG,
                            highlightthickness=0, bd=0)
        self.cv.pack()
        self.sound = Sound()
        self.api = RngClient(API_URL)
        self.families = set(tkfont.families(root))
        self._make_fonts()
        self._reel_fonts = {}

        self.machines = [Machine(self, 0, "classical"), Machine(self, 1, "quantum")]
        self._draw_footer()
        self._bind()
        self.sound.prepare_spin(N_DIGITS)
        self.ping_job = None
        self.footer_state = None
        self.ping()

        self.last = time.perf_counter()
        self._tick()

    # -- fonts --------------------------------------------------------------
    def font(self, families, px, weight="normal"):
        family = next((f for f in families if f in self.families), "Helvetica")
        return tkfont.Font(self.root, family=family, size=-max(6, round(px * self.k)),
                           weight=weight)

    def reel_font(self, px):
        if px not in self._reel_fonts:
            self._reel_fonts[px] = self.font(DIGIT_FONTS, px, "bold")
        return self._reel_fonts[px]

    def _make_fonts(self):
        self.f_title = self.font(TITLE_FONTS, 40, "bold")
        size = -self.f_title.cget("size")
        widest = max((t["title"] for t in THEMES.values()), key=self.f_title.measure)
        while self.f_title.measure(widest) > 300 * self.k and size > 10:
            size -= 1
            self.f_title.configure(size=-size)
        self.f_label = self.font(UI_FONTS, 13, "bold")
        self.f_button = self.font(UI_FONTS, 26, "bold")
        self.f_history = self.font(UI_FONTS, 16, "bold")
        self.f_small = self.font(UI_FONTS, 12)
        self.f_small_bold = self.font(UI_FONTS, 12, "bold")
        self.f_tiny = self.font(UI_FONTS, 10)
        self.f_led_big = self.font(LED_FONTS, 46, "bold")
        self.f_led_msg = self.font(LED_FONTS, 25, "bold")
        self.f_led_mid = self.font(LED_FONTS, 18, "bold")
        self.f_led_small = self.font(LED_FONTS, 12, "bold")
        self.f_led_tiny = self.font(LED_FONTS, 10, "bold")

    # -- footer and input ---------------------------------------------------
    def _draw_footer(self):
        y = 752 * self.k
        self.status_text = self.cv.create_text(30 * self.k, y, text="", anchor="w",
                                               font=self.f_small_bold, fill=STATUS_DIM,
                                               tags=("apistatus",))
        self.hint_text = self.cv.create_text((W - 30) * self.k, y, anchor="e", font=self.f_small,
                                             fill=STATUS_DIM, tags=("soundbtn",))
        self._update_hint()

    def _update_hint(self):
        hint = "SPACE spins both  ·  1 classical  ·  2 quantum"
        if self.sound.available:
            hint += f"  ·  M sound {'on' if self.sound.enabled else 'off'}"
        self.cv.itemconfigure(self.hint_text, text=hint)

    def _bind(self):
        cv = self.cv
        cv.bind("<ButtonPress-1>", lambda e: cv.focus_set(), add="+")
        cv.bind("<B1-Motion>", lambda e: [m.on_drag(e) for m in self.machines])
        cv.bind("<ButtonRelease-1>", lambda e: [m.on_release(e) for m in self.machines])
        for tag, action in (("apistatus", self.ping), ("soundbtn", self.toggle_sound)):
            cv.tag_bind(tag, "<ButtonPress-1>", lambda e, a=action: a())
            cv.tag_bind(tag, "<Enter>", lambda e: cv.configure(cursor="hand2"))
            cv.tag_bind(tag, "<Leave>", lambda e: cv.configure(cursor=""))

        root = self.root
        for key in ("<space>", "<Return>", "<KP_Enter>"):
            root.bind(key, lambda e: self.pull_all())
        for key, i in (("<KeyPress-1>", 0), ("<KP_1>", 0), ("<KeyPress-2>", 1), ("<KP_2>", 1)):
            root.bind(key, lambda e, i=i: self.machines[i].pull())
        for key in ("<KeyPress-m>", "<KeyPress-M>"):
            root.bind(key, lambda e: self.toggle_sound())

    def pull_all(self):
        for machine in self.machines:
            machine.pull()

    def toggle_sound(self):
        self.sound.toggle()
        self._update_hint()

    def ping(self):
        if self.ping_job is None or self.ping_job.done:
            self.ping_job = Job(self.api.ping)

    def _update_footer(self):
        mode = "checking" if self.ping_job and not self.ping_job.done else self.api.mode
        if mode == "online":
            state = (f"● API ONLINE  {API_URL}", LED_GOOD)
        elif mode == "local":
            state = (f"● LOCAL MODE: no API at {API_URL}. "
                     "Start it with python rng_api.py, then click here.", AMBER)
        else:
            state = ("● CHECKING API…", STATUS_DIM)
        if state != self.footer_state:
            self.footer_state = state
            self.cv.itemconfigure(self.status_text, text=state[0], fill=state[1])

    # -- frame loop ---------------------------------------------------------
    def _tick(self):
        now = time.perf_counter()
        dt = max(1e-3, now - self.last)
        self.last = now
        try:
            for machine in self.machines:
                machine.update(now, dt)
            self._update_footer()
        finally:  # a bug in one frame shouldn't freeze the whole window
            self.frame_job = self.root.after(15, self._tick)

    def close(self):
        self.root.after_cancel(self.frame_job)
        self.sound.close()
        self.root.destroy()


def main():
    if sys.platform == "win32":  # crisp rendering on scaled displays
        try:
            import ctypes
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(1)
            except Exception:
                ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass
    root = tk.Tk()
    scale = root.winfo_fpixels("1i") / 96.0
    scale = min(scale, root.winfo_screenheight() * 0.88 / H, root.winfo_screenwidth() * 0.9 / W)
    App(root, max(0.5, scale))
    root.mainloop()


if __name__ == "__main__":
    main()
