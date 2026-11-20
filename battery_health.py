"""Battery history and a rough health estimate for the AULA F75.

The keyboard only reports charge % and a charging flag (dongle cmd 0x4A). There is no health
register, so health is *estimated*: we log readings while the keyboard is in use and compare how
fast it actually drains (per hour awake) and charges against a new battery with the official specs:

    4000 mAh, ~17.5 h with default lighting (~229 mA), ~266.5 h with lights off (~15 mA),
    charging at 5 V / 700 mA.

Readings are only taken while someone is already typing (see ActivityWatcher), because any read
resets the keyboard's sleep timer: polling an idle keyboard would keep it awake and drain it.
"""
import json, os, select, threading, time

CAPACITY_MAH = 4000
I_OFF_MA = CAPACITY_MAH / 266.5          # ~15 mA: radio + controller, lights off
I_FULL_MA = CAPACITY_MAH / 17.5          # ~229 mA: default lighting (full brightness)
I_CHARGE_MA = 700 * 0.9                  # rated charge current, minus conversion losses
MIN_CHANGE = 10                          # % of observed change before an estimate is shown
GOOD_CHANGE = 40                         # % of observed change for a "good" confidence

LOG_DIR = os.path.join(os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share")), "aula-f75")
LOG_PATH = os.path.join(LOG_DIR, "battery-log.jsonl")


# ------------------------------------------------------------------ log
def append(sample):
    os.makedirs(LOG_DIR, exist_ok=True)
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(sample, separators=(",", ":")) + "\n")


def load():
    try:
        with open(LOG_PATH) as f:
            return [json.loads(line) for line in f if line.strip()]
    except (OSError, ValueError):
        return []


def last_awake():
    s = load()
    return s[-1]["awake"] if s else 0.0


def reset():
    try:
        os.remove(LOG_PATH)
    except OSError:
        pass


# ------------------------------------------------------------------ model
def draw_ma(mode, brightness):
    """Estimated current for a lighting setting. Effects that light fewer keys use less, so this
    over-estimates for sparse effects (reactive, raindrops...), which makes health read low."""
    if not mode or not brightness:
        return I_OFF_MA
    return I_OFF_MA + (I_FULL_MA - I_OFF_MA) * brightness / 9


def estimate(samples=None):
    """-> dict with health % (or None), confidence, and how much data backs it."""
    s = samples if samples is not None else load()
    d_obs = d_exp = 0.0          # discharge: observed % vs % a new battery would have used
    c_pct = c_hours = 0.0        # charging: % gained over wall-clock hours
    for a, b in zip(s, s[1:]):
        if not a["chg"] and not b["chg"]:
            drop, hours = a["pct"] - b["pct"], (b["awake"] - a["awake"]) / 3600
            if drop < 0 or hours <= 0 or hours > 48:
                continue                      # charged while we weren't looking, or a gap
            d_obs += drop
            d_exp += draw_ma(a["mode"], a["bri"]) * hours / CAPACITY_MAH * 100
        elif a["chg"] and b["chg"] and 5 <= a["pct"] and b["pct"] <= 85:
            gain, hours = b["pct"] - a["pct"], (b["t"] - a["t"]) / 3600
            if gain > 0 and 0 < hours < 12:   # constant-current part of the charge only
                c_pct += gain
                c_hours += hours

    parts = []
    if d_obs >= MIN_CHANGE / 2 and d_exp > 0:
        parts.append((d_exp / d_obs * 100, d_obs))
    if c_pct >= MIN_CHANGE / 2:
        # a new battery gains I_CHARGE / CAPACITY per hour; slower gains mean... a *bigger* battery,
        # faster gains mean less capacity left
        expected_gain = I_CHARGE_MA / CAPACITY_MAH * 100 * c_hours
        parts.append((expected_gain / c_pct * 100, c_pct))
    observed = d_obs + c_pct
    out = {"samples": len(s), "observedDischarge": round(d_obs, 1), "observedCharge": round(c_pct, 1),
           "needed": MIN_CHANGE, "health": None, "low": None, "high": None, "confidence": "collecting"}
    if not parts or observed < MIN_CHANGE:
        return out
    w = sum(n for _, n in parts)
    health = sum(h * n for h, n in parts) / w
    spread = 30 if observed < 20 else 20 if observed < GOOD_CHANGE else 12
    out.update(health=round(min(health, 110)), low=round(max(0, health - spread)), high=round(min(110, health + spread)),
               confidence="rough" if observed < GOOD_CHANGE else "fair")
    return out


# ------------------------------------------------------------------ typing activity
class ActivityWatcher(threading.Thread):
    """Notices *that* the keyboard is in use, never *what* is typed: it only records the time of
    the latest input report on the receiver's keyboard interfaces (vendor replies, report 0x13,
    are ignored). Reading these nodes doesn't wake the keyboard or change its sleep timer."""

    def __init__(self, nodes_fn, vendor_rid=0x13):
        super().__init__(daemon=True)
        self.nodes_fn, self.vendor_rid = nodes_fn, vendor_rid
        self.last = 0.0
        self.awake_until = 0.0
        self.awake_total = 0.0       # seconds the keyboard was (probably) awake, see note()
        self.sleep_s = 60
        self._lock = threading.Lock()

    def idle_for(self):
        return time.time() - self.last

    def note(self, now):
        """The keyboard stays awake sleep_s after the last key press; count the union of those spans."""
        with self._lock:
            end = now + self.sleep_s
            if end > self.awake_until:
                self.awake_total += end - max(now, self.awake_until)
                self.awake_until = end
            self.last = now

    def awake_seconds(self):
        """Awake time so far, not counting the part of the current span that hasn't happened yet."""
        with self._lock:
            return self.awake_total - max(0.0, self.awake_until - time.time())

    def run(self):
        fds = {}
        while True:
            if not fds:
                for path in self.nodes_fn():
                    try:
                        fds[os.open(path, os.O_RDONLY | os.O_NONBLOCK)] = path
                    except OSError:
                        pass
                if not fds:
                    time.sleep(5)
                    continue
            try:
                ready = select.select(list(fds), [], [], 5)[0]
            except (OSError, ValueError):
                ready = list(fds)
            for fd in ready:
                try:
                    b = os.read(fd, 64)
                except BlockingIOError:
                    continue
                except OSError:          # receiver unplugged: reopen later
                    for f in fds:
                        try:
                            os.close(f)
                        except OSError:
                            pass
                    fds = {}
                    break
                if b and not (len(b) == 20 and b[0] == self.vendor_rid):
                    self.note(time.time())
