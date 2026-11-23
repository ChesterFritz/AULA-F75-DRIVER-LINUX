#!/usr/bin/env python3
"""AULA F75 desktop app backend: local HTTP + JSON API over aula_f75.py.

Listens on 127.0.0.1 only; every API call must carry the per-launch token,
so other web pages in the browser cannot talk to the keyboard.
"""
import glob, json, os, secrets, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.realpath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import aula_f75 as A  # noqa: E402
import battery_health as H  # noqa: E402
import keychron_mouse as KM  # noqa: E402

# Notices typing (timestamps only) so battery reads happen only while the keyboard is in use:
# every read resets the keyboard's sleep timer, so polling an idle keyboard would keep it awake.
ACTIVITY = H.ActivityWatcher(A.activity_nodes)
LAST_BATTERY = [None]

STATIC = os.path.join(HERE, "static")
BACKUP_DIR = os.path.join(ROOT, "backups")
TOKEN = secrets.token_urlsafe(24)
LOCK = threading.Lock()
LAST_PING = [time.time()]
_dev = [None]


class NoDevice(Exception):
    pass


def device():
    if _dev[0] is None:
        for cls in (A.Wired, A.Dongle):
            d = cls.find()
            if d:
                _dev[0] = d
                break
        else:
            raise NoDevice("Keyboard not found. Plug in the 2.4G receiver or the USB cable.")
    return _dev[0]


def drop_device():
    d = _dev[0]
    _dev[0] = None
    if d:
        try:
            os.close(d.fd)
        except OSError:
            pass


def with_device(fn):
    """Run fn(dev) under the lock; reopen once if the handle went stale."""
    with LOCK:
        for attempt in (0, 1):
            try:
                return fn(device())
            except OSError:
                drop_device()
                if attempt:
                    raise NoDevice("Lost the keyboard connection. Replug the receiver and try again.")


# ------------------------------------------------------------------ state
def led_state(led, pal):
    modes = {}
    for m in A.MODES:
        b, s, c = A.decode(led, m)
        colors = [pal[m * 21 + i * 3: m * 21 + i * 3 + 3].hex() for i in range(7)] if len(pal) >= A.PAL_LEN else []
        modes[m] = {"brightness": b, "speed": s, "color": c, "palette": colors}
    return {"mode": led[0x0A], "modes": modes, "sleep": A.sleep_seconds(led)}


def layer_state(m, factory):
    keys = {}
    for k, i in A.PHYS.items():
        code = bytes(m[i * 4:i * 4 + 4])
        fac = factory[i * 4:i * 4 + 4] if factory else code
        keys[k] = {"action": A.decode_action(code), "raw": code.hex(),
                   "changed": code != fac, "default": A.decode_action(fac)}
    return keys


def full_state(dev):
    led = dev.get_led()
    A.check_led(led)
    pal = dev.get_palette()
    try:
        fk = json.load(open(os.path.join(ROOT, "factory-keys.json")))
    except OSError:
        fk = {}
    layers = {}
    for name, n in A.LAYERS.items():
        fac = bytes.fromhex(fk[f"matrix{n}"]) if f"matrix{n}" in fk else None
        layers[name] = layer_state(A.read_layer(dev, n), fac)
    macros = [{"id": i, "name": nm, "events": A.describe_events(ev)}
              for i, (nm, ev) in enumerate(A.parse_macros(dev.get_macros()))]
    v = dev.version()
    return {"connected": True, "kind": dev.kind, "firmware": v, "battery": battery_state(dev),
            "lighting": led_state(led, pal), "layers": layers, "macros": macros}


def battery_state(dev):
    try:
        b = dev.battery()
    except A.DeviceError:
        return LAST_BATTERY[0]
    if b:
        LAST_BATTERY[0] = b
    return b


def battery_live():
    """Fresh reading only if the keyboard was used in the last 20 s; otherwise the last one."""
    if ACTIVITY.idle_for() > 20 and LAST_BATTERY[0] is not None:
        return LAST_BATTERY[0]
    return with_device(battery_state)


def logger_running():
    import subprocess
    try:
        return subprocess.run(["systemctl", "--user", "is-active", "--quiet", "aula-f75-battery.service"],
                              timeout=3).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def battery_health():
    log = H.load()
    return {"estimate": H.estimate(log), "logging": logger_running(),
            "lastReading": log[-1] if log else None,
            "specs": {"capacity": H.CAPACITY_MAH, "hoursLit": 17.5, "hoursDark": 266.5}}


def catalog():
    return {
        "modes": [{"id": k, "name": v[0], "speed": v[1], "color": v[2]} for k, v in A.MODES.items()],
        "colors": A.COLORS,
        "media": list(A.MEDIA),
        "keys": sorted(A.HID, key=lambda k: A.HID[k]),
        "mods": list(A.MODS),
        "macroModes": list(A.MACRO_MODES),
        "sleepChoices": A.SLEEP_CHOICES,
    }


# ---------------------------------------------------------------- actions
def act_lighting(dev, body):
    led = bytearray(dev.get_led())
    A.check_led(led)
    m = int(body["mode"])
    if m not in A.MODES and m != A.OFF:
        raise A.DeviceError("unsupported mode")
    led[0x0A] = m
    if m in A.MODES:
        bi, si = 0x3A + 2 * (m - 1), 0x3B + 2 * (m - 1)
        b, s, c = led[bi], led[si] >> 4, led[si] & 0x0F
        if "brightness" in body: b = max(0, min(9, int(body["brightness"])))
        if "speed" in body: s = max(0, min(4, int(body["speed"])))
        if "color" in body and A.MODES[m][2]: c = max(0, min(7, int(body["color"])))
        led[bi], led[si] = b, (s << 4) | c
    dev.set_led(bytes(led))


def act_palette(dev, body):
    tab = bytearray(dev.get_palette())[:A.PAL_LEN]
    m, slot = int(body["mode"]), int(body["slot"])
    if m not in A.MODES or not 0 <= slot <= 6:
        raise A.DeviceError("bad palette slot")
    rgb = bytes.fromhex(body["rgb"].lstrip("#"))
    o = m * 21 + slot * 3
    tab[o:o + 3] = rgb
    dev.set_palette(bytes(tab))


def act_remap(dev, body):
    layer = A.LAYERS[body["layer"]]
    slot = A.phys_slot(body["key"])
    action = body["action"]
    if action == "default":
        fk = json.load(open(os.path.join(ROOT, "factory-keys.json")))
        code = bytes.fromhex(fk[f"matrix{layer}"])[slot * 4:slot * 4 + 4]
    else:
        code = A.encode_action(action)
    if layer == 0 and slot == A.PHYS["fn"]:
        raise A.DeviceError("The Fn key can't be remapped here, or you would lose the Fn layer.")
    m = A.read_layer(dev, layer)
    m[slot * 4:slot * 4 + 4] = code
    dev.set_matrix(layer, bytes(m))
    time.sleep(0.1)
    if bytes(A.read_layer(dev, layer)[slot * 4:slot * 4 + 4]) != code:
        raise A.DeviceError("The keyboard did not keep the new key. Try again.")


def act_reset_keys(dev, body):
    fk = json.load(open(os.path.join(ROOT, "factory-keys.json")))
    for layer in (0, 1):
        d = bytes.fromhex(fk[f"matrix{layer}"])
        dev.set_matrix(layer, d + bytes(A.MATRIX_LEN - len(d)))


def act_macro(dev, body):
    macros = A.parse_macros(dev.get_macros())
    if body["op"] == "set":
        mid = int(body["id"])
        if mid > len(macros):
            raise A.DeviceError(f"The next free macro number is {len(macros)}.")
        events = A.compile_macro(body["spec"], int(body.get("gap", 15)))
        entry = ((body.get("name") or f"Macro {mid}")[:30], events)
        if mid == len(macros):
            macros.append(entry)
        else:
            macros[mid] = entry
    elif body["op"] == "delete":
        if int(body["id"]) != len(macros) - 1:
            raise A.DeviceError("Only the last macro can be deleted, so keys bound to the others keep working.")
        macros.pop()
    buf = A.build_macros(macros)
    dev.set_macros(buf)
    time.sleep(0.1)
    if dev.get_macros()[:len(buf)] != buf:
        raise A.DeviceError("Macro memory did not read back correctly. Try again.")


def act_backup(dev, body):
    os.makedirs(BACKUP_DIR, exist_ok=True)
    name = time.strftime("backup-%Y-%m-%d-%H%M%S.json")

    class Args: file = os.path.join(BACKUP_DIR, name)
    A.cmd_backup(dev, Args)
    return {"file": name}


def list_backups():
    files = []
    for p in sorted(glob.glob(os.path.join(BACKUP_DIR, "*.json")), reverse=True):
        files.append({"file": os.path.basename(p), "label": os.path.basename(p), "dir": "backups"})
    for p in ("before-remap.json", "original.af75"):
        if os.path.exists(os.path.join(ROOT, p)):
            files.append({"file": p, "dir": "root",
                          "label": {"before-remap.json": "Before key changes",
                                    "original.af75": "Original lighting"}[p]})
    return files


def act_restore(dev, body):
    base = BACKUP_DIR if body.get("dir") == "backups" else ROOT
    name = os.path.basename(body["file"])
    path = os.path.join(base, name)
    if not os.path.isfile(path):
        raise A.DeviceError("That backup file no longer exists.")

    class Args: file = path
    A.cmd_restore(dev, Args)


def act_sleep(dev, body):
    led = bytearray(dev.get_led())
    A.check_led(led)
    sec = int(body["seconds"])
    if sec != 0 and sec not in A.SLEEP_CHOICES:
        raise A.DeviceError("Unsupported sleep time.")
    led[A.SLEEP_OFF] = sec // 30
    dev.set_led(bytes(led))


ACTIONS = {"sleep": act_sleep, "lighting": act_lighting, "palette": act_palette, "remap": act_remap,
           "reset-keys": act_reset_keys, "macro": act_macro, "backup": act_backup,
           "restore": act_restore}

MIME = {".html": "text/html; charset=utf-8", ".css": "text/css", ".js": "text/javascript",
        ".png": "image/png", ".svg": "image/svg+xml", ".json": "application/json", ".ttf": "font/ttf"}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, code, obj):
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass  # the page closed or reloaded before the answer arrived; nothing to do

    def _authed(self):
        return secrets.compare_digest(self.headers.get("X-Token", ""), TOKEN)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path.startswith("/api/mouse-image/"):
            q = dict(x.split("=", 1) for x in self.path.partition("?")[2].split("&") if "=" in x)
            if not secrets.compare_digest(q.get("t", ""), TOKEN):
                return self._json(403, {"error": "forbidden"})
            try:
                pid, n = path.split("/")[-2:]
                art = KM.artwork(int(pid, 16))
                data = open(art["images"][int(n)], "rb").read()
            except (ValueError, IndexError, TypeError, OSError):
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Cache-Control", "max-age=86400")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if path.startswith("/api/"):
            if not self._authed():
                return self._json(403, {"error": "forbidden"})
            LAST_PING[0] = time.time()
            try:
                if path == "/api/ping":
                    return self._json(200, {"ok": True})
                if path == "/api/catalog":
                    return self._json(200, catalog())
                if path == "/api/backups":
                    return self._json(200, list_backups())
                if path == "/api/state":
                    return self._json(200, with_device(full_state))
                if path == "/api/battery":
                    return self._json(200, {"battery": battery_live()})
                if path == "/api/battery-health":
                    return self._json(200, battery_health())
                if path == "/api/mouse-info":
                    try:
                        return self._json(200, with_mouse(mouse_info))
                    except KM.MouseError:
                        return self._json(200, {"info": None})
                if path == "/api/mouse":
                    try:
                        st = with_mouse(mouse_state)
                        return self._json(200, dict(st, catalog=mouse_catalog(), art=mouse_art(st["pid"])))
                    except KM.MouseError as e:
                        return self._json(200, {"connected": False, "error": str(e), "catalog": mouse_catalog()})
            except NoDevice as e:
                return self._json(200, {"connected": False, "error": str(e)})
            except A.DeviceError as e:
                return self._json(200, {"connected": False, "error": wake_hint(e)})
            return self._json(404, {"error": "not found"})
        if path == "/":
            path = "/index.html"
        f = os.path.realpath(os.path.join(STATIC, path.lstrip("/")))
        if not f.startswith(STATIC + os.sep) or not os.path.isfile(f):
            self.send_error(404)
            return
        data = open(f, "rb").read()
        self.send_response(200)
        self.send_header("Content-Type", MIME.get(os.path.splitext(f)[1], "application/octet-stream"))
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        if not self.path.startswith("/api/") or not self._authed():
            return self._json(403, {"error": "forbidden"})
        LAST_PING[0] = time.time()
        name = self.path[len("/api/"):]
        if name == "mouse-settings":
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                return self._json(200, dict(with_mouse(lambda m: act_mouse_settings(m, body)), ok=True))
            except KM.MouseError as e:
                return self._json(200, {"ok": False, "error": str(e)})
            except (KeyError, ValueError, TypeError) as e:
                return self._json(400, {"ok": False, "error": f"Bad request: {e}"})
        if name == "mouse-remap":
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                return self._json(200, dict(with_mouse(lambda m: act_mouse_remap(m, body)), ok=True))
            except KM.MouseError as e:
                return self._json(200, {"ok": False, "error": str(e)})
            except (KeyError, ValueError) as e:
                return self._json(400, {"ok": False, "error": f"Bad request: {e}"})
        fn = ACTIONS.get(name)
        if not fn:
            return self._json(404, {"error": "not found"})
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            res = with_device(lambda d: fn(d, body)) or {}
            return self._json(200, dict(res, ok=True))
        except NoDevice as e:
            return self._json(200, {"ok": False, "error": str(e)})
        except A.DeviceError as e:
            return self._json(200, {"ok": False, "error": wake_hint(e)})
        except (KeyError, ValueError) as e:
            return self._json(400, {"ok": False, "error": f"Bad request: {e}"})


# ---------------------------------------------------------------- Keychron mouse
# Separate handle and lock from the keyboard, so a missing or sleeping mouse never
# gets in the way of the AULA keyboard.
MOUSE_LOCK = threading.Lock()
_mouse = [None]


def with_mouse(fn):
    with MOUSE_LOCK:
        for attempt in (0, 1):
            if _mouse[0] is None:
                _mouse[0] = KM.Receiver.find()
                if _mouse[0] is None:
                    raise KM.MouseError("Keychron mouse not found. Plug in the Keychron receiver or the cable.")
            try:
                return fn(_mouse[0])
            except OSError:
                _mouse[0].close()
                _mouse[0] = None
                if attempt:
                    raise KM.MouseError("Lost the Keychron receiver. Plug it back in.")


def _mouse_info(m, pid):
    art = KM.artwork(pid)
    try:
        return m.info(art["rates"] if art else None)
    except KM.MouseError:
        return None


def mouse_state(m):
    name, rows = m.buttons()
    pid = m.model()
    return {"connected": True, "name": name, "pid": pid, "buttons": rows, "info": _mouse_info(m, pid)}


def mouse_info(m):
    return {"info": _mouse_info(m, m.model())}


def mouse_art(pid):
    """Keychron's pictures of the mouse (downloaded once, outside the mouse lock)."""
    art = KM.artwork(pid)
    return {"images": len(art["images"]), "spots": art["spots"], "dpi_limit": art.get("dpi_limit")} if art else None


def mouse_catalog():
    return {"mouse": list(KM.MOUSE_ACTIONS), "media": list(KM.MEDIA_ACTIONS),
            "cycle": list(KM.CYCLE_ACTIONS), "shortcut": list(KM.SHORTCUT_ACTIONS)}


def act_mouse_remap(m, body):
    return {"action": m.remap(body["button"], body["action"])}


def act_mouse_settings(m, body):
    """{"dpi": {"steps": [...], "current": n}} and/or {"polling": n}; returns the fresh info."""
    pid = m.model()
    art = KM.artwork(pid)
    if "dpi" in body:
        d = body["dpi"]
        limit = tuple(art["dpi_limit"]) if art and art.get("dpi_limit") else (50, 26000)
        m.set_dpi(d["steps"], int(d["current"]), limit)
    if "polling" in body:
        m.set_polling(int(body["polling"]))
    return {"info": _mouse_info(m, pid)}


def wake_hint(e):
    s = str(e)
    if "asleep" in s or "not acknowledged" in s or "failed" in s:
        return "The keyboard didn't answer. Press any key to wake it, then try again."
    return s[0].upper() + s[1:] if s else "Unknown error"


def serve(port=0):
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    if not ACTIVITY.is_alive():
        ACTIVITY.start()
    return srv


def watchdog(srv, idle=25):
    """Exit when the app window has stopped pinging for `idle` seconds."""
    while True:
        time.sleep(3)
        if time.time() - LAST_PING[0] > idle:
            srv.shutdown()
            return


if __name__ == "__main__":
    srv = serve()
    port = srv.server_address[1]
    print(f"http://127.0.0.1:{port}/?t={TOKEN}", flush=True)
    threading.Thread(target=watchdog, args=(srv,), daemon=True).start()
    srv.serve_forever()
