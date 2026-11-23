#!/usr/bin/env python3
"""Keychron mouse button remapping on Linux (tested target: Keychron M6 via the Link-KM receiver).

Protocol taken from Keychron Launcher (launcher.keychron.com, v1.5.5), the "default" mouse
protocol used by current receivers:

  * HID interface with vendor usage page 0xFFC1 (or 0xFF0A) on vendor 0x3434.
  * Output report 0xB5 (20 bytes) [0x03]          -> input 0xB6: receiver status, up to 3
    paired devices as [vid lo, vid hi, pid lo, pid hi, on] starting at byte 2.
  * Output report 0xB3 (63 bytes) [0x62, button]  -> input 0xB4 [0x62, button, 0, type, data...]
    reads one button (0x66 for the Fn layer).
  * Output report 0xB3 [0x52, button, 0, type, data...] writes one button (0x56 for Fn);
    the M6 confirms on the short input report: 0xB6 [0xE4, 0x00, 0x52].

Button function types: 0 default, 1 mouse button, 2 keyboard, 3 media, 5 DPI,
8 shortcut, 9 disabled, 13 polling rate.
"""
import argparse, glob, json, os, select, sys, time

VID = 0x3434
RID_SHORT_OUT, RID_SHORT_IN = 0xB5, 0xB6     # 20-byte reports
RID_LONG_OUT, RID_LONG_IN = 0xB3, 0xB4       # 63-byte reports
CMD_STATUS, CMD_GET, CMD_SET = 0x03, 0x62, 0x52

T_DEFAULT, T_MOUSE, T_KEYBOARD, T_MEDIA, T_DPI, T_SHORTCUT, T_DISABLE, T_POLL = 0, 1, 2, 3, 5, 8, 9, 13


class MouseError(Exception):
    pass


# Per-model button layout (id, firmware index), from Keychron's device file
# static/device/<vid*65536+pid>/json/v3.json.
MODELS = {
    0xD064: ("Keychron M6", [
        ("left", 0), ("right", 2), ("middle", 1), ("forward", 4), ("backward", 3),
        ("leftTilt", 9), ("rightTilt", 8), ("upScroll", 14), ("downScroll", 13),
        ("leftScroll", 11), ("rightScroll", 10),
    ]),
}
BUTTON_LABEL = {
    "left": "Left button", "right": "Right button", "middle": "Wheel click", "forward": "Forward (side)",
    "backward": "Back (side)", "leftTilt": "Wheel tilt left", "rightTilt": "Wheel tilt right",
    "upScroll": "Scroll up", "downScroll": "Scroll down", "leftScroll": "Side wheel left",
    "rightScroll": "Side wheel right",
}

# type 1: 3 bytes, big-endian
MOUSE_ACTIONS = {
    "left": 0x010000, "right": 0x020000, "middle": 0x040000, "back": 0x080000, "forward": 0x100000,
    "double-left": 0x800000, "scroll-up": 0x000200, "scroll-down": 0x00FE00,
    "scroll-left": 0x0000FE, "scroll-right": 0x000002,
}
# type 3: HID consumer usage, 2 bytes little-endian
MEDIA_ACTIONS = {"volup": 0xE9, "voldown": 0xEA, "mute": 0xE2, "play": 0xCD, "prev": 0xB6,
                 "next": 0xB5, "stop": 0xB7, "media_player": 0x183}
# types 5 and 13: 2 bytes little-endian
CYCLE_ACTIONS = {"loop": 1, "next": 2, "prev": 3}
# type 8: firmware shortcuts, 3 bytes big-endian
SHORTCUT_ACTIONS = {
    "brightness-up": 814848, "brightness-down": 815104, "calculator": 823809, "my-computer": 824321,
    "home-page": 795394, "email": 821761, "refresh": 458814, "switch-app": 459819, "task-view": 827138,
    "screenshot": 461334, "copy": 459014, "cut": 459035, "paste": 459033,
    "zoom-out": 459053, "zoom-in": 459054,
}
MODS = {"lctrl": 0x01, "lshift": 0x02, "lalt": 0x04, "lwin": 0x08,
        "rctrl": 0x10, "rshift": 0x20, "ralt": 0x40, "rwin": 0x80}


def _be3(v): return [(v >> 16) & 0xFF, (v >> 8) & 0xFF, v & 0xFF]
def _le2(v): return [v & 0xFF, (v >> 8) & 0xFF]


def _hid_tables():
    # Reuse the AULA tool's keyboard names so both devices speak the same key language.
    sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
    import aula_f75 as A
    return A.HID, A.HID_NAME, A.norm


def encode(spec):
    """Text action -> (type, data bytes). Examples: default, disable, mouse:back,
    media:volup, dpi:loop, poll:next, shortcut:copy, ctrl+shift+t, pgdn."""
    s = spec.strip().lower()
    if s == "default":
        return T_DEFAULT, []
    if s in ("disable", "off", "none"):
        return T_DISABLE, []
    kind, _, arg = s.partition(":")
    table = {"mouse": (T_MOUSE, MOUSE_ACTIONS, _be3), "media": (T_MEDIA, MEDIA_ACTIONS, _le2),
             "dpi": (T_DPI, CYCLE_ACTIONS, _le2), "poll": (T_POLL, CYCLE_ACTIONS, _le2),
             "shortcut": (T_SHORTCUT, SHORTCUT_ACTIONS, _be3)}
    if arg and kind in table:
        t, names, pack = table[kind]
        if arg not in names:
            raise MouseError(f"unknown {kind} action {arg!r}; choose from {', '.join(names)}")
        return t, pack(names[arg])
    HID, _, norm = _hid_tables()
    mods, keys = 0, []
    for p in s.split("+"):
        p = norm(p)
        if p in MODS:
            mods |= MODS[p]
        elif p in HID:
            keys.append(HID[p])
        else:
            raise MouseError(f"unknown key {p!r} in {spec!r}")
    if len(keys) > 2:
        raise MouseError("at most two keys plus modifiers")
    return T_KEYBOARD, [mods] + keys


def decode(t, d):
    """(type, data bytes) -> text action, the inverse of encode()."""
    d = list(d) + [0] * 6
    if t == T_DEFAULT:
        return "default"
    if t == T_DISABLE:
        return "disable"
    if t == T_KEYBOARD:
        _, HID_NAME, _ = _hid_tables()
        parts = [n for n, bit in MODS.items() if d[0] & bit]
        parts += [HID_NAME.get(k, f"0x{k:02x}") for k in d[1:3] if k]
        return "+".join(parts) or "default"
    rev = lambda names, v: next((n for n, x in names.items() if x == v), None)
    if t == T_MOUSE:
        n = rev(MOUSE_ACTIONS, (d[0] << 16) | (d[1] << 8) | d[2])
    elif t == T_MEDIA:
        n = rev(MEDIA_ACTIONS, d[0] | (d[1] << 8))
    elif t in (T_DPI, T_POLL):
        n = rev(CYCLE_ACTIONS, d[0] | (d[1] << 8))
    elif t == T_SHORTCUT:
        n = rev(SHORTCUT_ACTIONS, (d[0] << 16) | (d[1] << 8) | d[2])
    else:
        n = None
    kind = {T_MOUSE: "mouse", T_MEDIA: "media", T_DPI: "dpi", T_POLL: "poll", T_SHORTCUT: "shortcut"}.get(t)
    if kind and n:
        return f"{kind}:{n}"
    return f"raw:{t}:{bytes(d[:4]).hex()}"


def _uevent(path):
    out = {}
    try:
        for line in open(path):
            k, _, v = line.strip().partition("=")
            out[k] = v
    except OSError:
        pass
    return out


def _is_mouse_channel(desc):
    # Vendor usage page 0xFFC1 or 0xFF0A, collection usage 1 (what the Launcher asks WebHID for).
    return b"\x06\xc1\xff\x09\x01" in desc or b"\x06\x0a\xff\x09\x01" in desc


class Receiver:
    """The vendor HID channel of a Keychron mouse or its 2.4 GHz receiver."""

    def __init__(self, path, name):
        self.path, self.name = path, name
        self.fd = os.open(path, os.O_RDWR)

    @classmethod
    def find(cls):
        for node in sorted(glob.glob("/sys/class/hidraw/hidraw*")):
            ue = _uevent(os.path.join(node, "device", "uevent"))
            hid_id = ue.get("HID_ID", "")
            if f":0000{VID:04X}:" not in hid_id.upper():
                continue
            try:
                desc = open(os.path.join(node, "device", "report_descriptor"), "rb").read()
            except OSError:
                continue
            if _is_mouse_channel(desc):
                try:
                    return cls("/dev/" + os.path.basename(node), ue.get("HID_NAME", "Keychron"))
                except PermissionError:
                    raise MouseError(f"No permission for /dev/{os.path.basename(node)}; "
                                     "install the udev rule (install.sh) and replug the receiver.")
        return None

    def close(self):
        try:
            os.close(self.fd)
        except OSError:
            pass

    def _drain(self):
        while select.select([self.fd], [], [], 0)[0]:
            os.read(self.fd, 64)

    def _ask(self, rid, size, payload, want, timeout=1.0):
        self._drain()
        os.write(self.fd, bytes([rid]) + bytes(payload) + bytes(size - len(payload)))
        end = time.time() + timeout
        while time.time() < end:
            if not select.select([self.fd], [], [], max(0, end - time.time()))[0]:
                break
            d = os.read(self.fd, 64)
            if want(d):
                return d
        raise MouseError("The mouse didn't answer. Move it to wake it up, then try again.")

    def devices(self):
        """Paired devices the receiver currently sees: [(vid, pid, connected)]."""
        d = self._ask(RID_SHORT_OUT, 20, [CMD_STATUS], lambda r: r[0] == RID_SHORT_IN and r[1] == CMD_STATUS)
        out = []
        for i in range(3):
            o = 3 + 5 * i
            vid, pid = d[o] | d[o + 1] << 8, d[o + 2] | d[o + 3] << 8
            if vid or pid:
                out.append((vid, pid, bool(d[o + 4])))
        return out

    def model(self):
        for vid, pid, on in self.devices():
            if on and vid == VID:
                if pid not in MODELS:
                    raise MouseError(f"Keychron mouse {pid:04x} is not supported yet (only the M6 is).")
                return pid
        raise MouseError("No mouse is connected to the Keychron receiver. Switch the mouse on.")

    def get(self, index, fn_layer=False):
        cmd = 0x66 if fn_layer else CMD_GET
        d = self._ask(RID_LONG_OUT, 63, [cmd, index],
                      lambda r: r[0] == RID_LONG_IN and r[1] == cmd and r[2] == index)
        return d[4], bytes(d[5:11])

    def set(self, index, t, data, fn_layer=False):
        cmd = 0x56 if fn_layer else CMD_SET
        self._ask(RID_LONG_OUT, 63, [cmd, index, 0, t] + list(data),
                  lambda r: r[0] in (RID_SHORT_IN, RID_LONG_IN) and r[1] == 0xE4 and r[3] == cmd)

    def work_mode(self):
        """0 = USB cable, 1 = 2.4 GHz receiver, 2 = Bluetooth (0xB3 [0x02] reply byte 9, low 3 bits)."""
        d = self._ask(RID_LONG_OUT, 63, [0x02, 0], lambda r: r[0] == RID_LONG_IN and r[1] == 0x02)
        return d[1 + 9] & 0x07

    def _raw_info(self):
        return self._ask(RID_LONG_OUT, 63, [0x06], lambda r: r[0] == RID_LONG_IN and r[1] == 0x06)[1:]

    def _write(self, payload):
        """Settings write on the long report; the mouse answers [0xE4, 0, cmd] or echoes cmd."""
        cmd = payload[0]
        self._ask(RID_LONG_OUT, 63, payload,
                  lambda r: r[0] in (RID_SHORT_IN, RID_LONG_IN) and (r[1] == cmd or (r[1] == 0xE4 and r[3] == cmd)))

    def set_dpi(self, steps, current, limit=(50, 26000)):
        """Store 1-5 DPI steps (multiples of 50) and make step `current` active (0x40, like Keychron Launcher)."""
        steps = [int(round(int(v) / 50) * 50) for v in steps]
        if not 1 <= len(steps) <= 5:
            raise MouseError("Pick between 1 and 5 DPI steps.")
        lo, hi = limit
        if any(not lo <= v <= hi for v in steps):
            raise MouseError(f"DPI must be between {lo} and {hi}.")
        if not 0 <= current < len(steps):
            raise MouseError("Pick one of the DPI steps.")
        data = [0x40, current, current, current]
        for v in steps + [0] * (5 - len(steps)):
            data += _le2(v)
        data.append(len(steps))
        self._write(data)
        p = self._raw_info()
        got = [p[5 + 2 * i] | p[6 + 2 * i] << 8 for i in range(p[16])]
        if got != steps:
            raise MouseError(f"The mouse kept {got} instead of {steps}.")

    def set_polling(self, current):
        """Make polling step `current` active, keeping the mouse's own list of rates (0x41)."""
        p = self._raw_info()
        count = max(1, min(p[49], 6))
        if not 0 <= current < count:
            raise MouseError("Pick one of the polling rates.")
        codes = list(p[43:43 + count])
        self._write([0x41, current, current] + codes + [0] * (6 - count) + [count])
        p = self._raw_info()
        if all((p[2 + m] >> 4) != current for m in range(3)):
            raise MouseError("The mouse didn't take the new polling rate.")

    def info(self, rates=None):
        """Device info (0xB3 [0x06]). Byte 19 = battery (low 7 bits %, bit 7 charging);
        bytes 2-4 = per connection mode: DPI step (low nibble), polling step (high nibble);
        5-14 = DPI steps (u16 LE), 16 = DPI step count; 43-48 = polling steps, 49 = their count.
        Polling steps index the model's report-rate list (`rates`, in Hz)."""
        d = self._ask(RID_LONG_OUT, 63, [0x06], lambda r: r[0] == RID_LONG_IN and r[1] == 0x06)
        p = d[1:]
        try:
            mode = self.work_mode()
        except MouseError:
            mode = 1
        sel = p[2 + min(mode, 2)]
        dpi_steps = [p[5 + 2 * i] | p[6 + 2 * i] << 8 for i in range(max(1, min(p[16], 5)))]
        poll_codes = list(p[43:43 + max(1, min(p[49], 6))])
        hz = [rates[c] if rates and c < len(rates) else None for c in poll_codes]
        return {"battery": {"percent": p[19] & 0x7F, "charging": bool(p[19] >> 7)},
                "dpi": {"steps": dpi_steps, "current": min(sel & 0x0F, len(dpi_steps) - 1)},
                "polling": {"steps": hz, "current": min(sel >> 4, len(hz) - 1)},
                "mode": ["USB cable", "2.4 GHz receiver", "Bluetooth"][min(mode, 2)]}

    def buttons(self):
        pid = self.model()
        name, layout = MODELS[pid]
        rows = []
        for bid, idx in layout:
            t, d = self.get(idx)
            rows.append({"id": bid, "index": idx, "label": BUTTON_LABEL.get(bid, bid), "action": decode(t, d)})
        return name, rows

    def remap(self, button, spec):
        pid = self.model()
        layout = dict(MODELS[pid][1])
        if button not in layout:
            raise MouseError(f"unknown button {button!r}; choose from {', '.join(layout)}")
        if button == "left" and spec.strip().lower() in ("disable", "off", "none"):
            raise MouseError("Turning off the left button would leave you without a way to click.")
        t, data = encode(spec)
        idx = layout[button]
        self.set(idx, t, data)
        got = self.get(idx)
        if got[0] != t or (t not in (T_DEFAULT, T_DISABLE) and list(got[1][:len(data)]) != list(data)):
            raise MouseError("The mouse did not keep the new setting.")
        return decode(*got)


# ------------------------------------------------------------- pictures
# Keychron's own product renders and button positions, downloaded from the public
# launcher server the first time (as Keychron Launcher does) and cached locally.
# They are Keychron's images, so they are never stored in this repository.
STATIC = "https://launcher.keychron.com/static/"
CACHE = os.path.join(os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache")), "aula-f75", "keychron")


def _get(url, timeout=15):
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


# Corrections to Keychron's published button positions (percent of the picture).
# M6: Keychron puts "right tilt" on the middle of the wheel; mirror "left tilt" across it instead.
SPOT_FIXES = {0xD064: {"rightTilt": {"x": 58.6, "y": 25.4}}}


def _fix_spots(pid, art):
    for bid, fix in SPOT_FIXES.get(pid, {}).items():
        if bid in art["spots"]:
            art["spots"][bid].update(fix)
    return art


def artwork(pid):
    """{"images": [local paths], "spots": {button: {"image": n, "x": %, "y": %}}} or None offline."""
    folder = os.path.join(CACHE, f"{pid:04x}")
    meta = os.path.join(folder, "artwork-v3.json")
    if os.path.exists(meta):
        return _fix_spots(pid, json.load(open(meta)))
    try:
        vpid = VID * 65536 + pid
        product = json.loads(_get(f"https://launcher.keychron.com/vapi/v2/product/{vpid}"))["data"]["product"]
        layout = json.loads(_get(f"{STATIC}device/{vpid}/json/v3.json"))
        os.makedirs(folder, exist_ok=True)
        images = []
        for i, path in enumerate(p for p in (product.get("cover") or "").split(",") if p):
            local = os.path.join(folder, f"{i}.png")
            data = _get(path if path.startswith("http") else STATIC + path.replace("upload/", "", 1))
            open(local, "wb").write(data)
            images.append(local)
        if not images:
            return None
        # "side": 1 marks buttons drawn on the second picture (the side view).
        spots = {k["id"]: {"image": min(int(k.get("side", 0)), len(images) - 1), "x": k["x"], "y": k["y"],
                           "dir": k.get("dir", "right")}
                 for k in layout.get("keys", [])}
        rates = [r["value"] if isinstance(r, dict) else r for r in layout.get("dpi", {}).get("reportRate", [])]
        limit = layout.get("dpi", {}).get("limit") or [50, 26000]
        out = {"images": images, "spots": spots, "rates": rates, "dpi_limit": limit}
        json.dump(out, open(meta, "w"))
        return _fix_spots(pid, out)
    except Exception:
        return None


def open_receiver():
    r = Receiver.find()
    if not r:
        raise MouseError("Keychron receiver or mouse not found.")
    return r


def main(argv=None):
    p = argparse.ArgumentParser(prog="keychron-mouse", description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status", help="show the receiver and paired devices")
    sub.add_parser("buttons", help="list what every button does")
    r = sub.add_parser("remap", help="change one button")
    r.add_argument("button")
    r.add_argument("action", help="default | disable | mouse:NAME | media:NAME | dpi:loop|next|prev | "
                                   "poll:loop|next|prev | shortcut:NAME | key combo like ctrl+c")
    sub.add_parser("names", help="list action names")
    sub.add_parser("json", help="dump buttons as JSON")
    a = p.parse_args(argv)
    if a.cmd == "names":
        print("mouse   :", ", ".join(MOUSE_ACTIONS))
        print("media   :", ", ".join(MEDIA_ACTIONS))
        print("dpi/poll:", ", ".join(CYCLE_ACTIONS))
        print("shortcut:", ", ".join(SHORTCUT_ACTIONS))
        print("other   : default, disable, or a key combo (ctrl+shift+t, pgdn)")
        return
    rcv = open_receiver()
    try:
        if a.cmd == "status":
            print(rcv.name, rcv.path)
            for vid, pid, on in rcv.devices():
                print(f"  {vid:04x}:{pid:04x}  {MODELS.get(pid, ('unknown',))[0]}  {'connected' if on else 'off'}")
        elif a.cmd in ("buttons", "json"):
            name, rows = rcv.buttons()
            if a.cmd == "json":
                print(json.dumps({"name": name, "buttons": rows}, indent=1))
            else:
                print(name)
                for b in rows:
                    print(f"  {b['id']:12s} -> {b['action']}")
        elif a.cmd == "remap":
            print(f"{a.button} -> {rcv.remap(a.button, a.action)}")
    finally:
        rcv.close()


if __name__ == "__main__":
    try:
        main()
    except MouseError as e:
        sys.exit(f"error: {e}")
