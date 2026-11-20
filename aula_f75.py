#!/usr/bin/env python3
"""
aula-f75 — Linux lighting control for the AULA F75 keyboard.

Protocol reverse-engineered from the vendor Windows driver (OemDrv.exe,
"BYCOMBO4", classes CDev3632 / CDevG5KB). No dependencies beyond Python 3.

Transports
  2.4G dongle 3554:fa09  vendor iface usage-page 0xFF02, report 0x13, 20-byte
                         output/input reports:
      write pkt: [13, cmd, nPkts, idx, (flag<<4)|len, data[14], sum8]
      read  req: [13, cmd|0x40, 1, 0, 0, ..., sum8]
      reply    : [13, cmd, nPkts|0x80 on error, idx, len, data[14], sum8]
  USB wired 258a:010c    vendor iface usage-page 0xFF00, feature report 0x06,
                         520 bytes: [06, cmd(|0x80 read), arg, 0, nChunks,
                         idx, lenLo, lenHi, data[512]]  (wired path untested)

LED config (128 bytes, magic 5A A5 at 126..127) is read-modify-written:
  [0x0A]           active hardware mode (0=off, 1..18 effects, 21=self-define)
  [0x18]           sleep timer in 30 s units (0 = never sleep); driver offers 2,3,4,6,8,10,20,30,40
  [0x3A + 2*(m-1)] brightness 0..9 for mode m
  [0x3B + 2*(m-1)] (speed 0..4) << 4 | color   (color 0..6 palette, 7 = rainbow)
Palette table: 21 bytes per mode (7 x RGB), slot 0 unused, mode m at m*21.
"""
import argparse, contextlib, fcntl, glob, os, select, sys, time

LOCK_PATH = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "aula-f75.lock")


@contextlib.contextmanager
def device_lock():
    """One request/reply exchange at a time across processes (app, CLI, battery logger),
    so nobody reads another process's reply off the shared receiver."""
    fd = os.open(LOCK_PATH, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)

VID_WIRED, PID_WIRED = 0x258A, 0x010C
VID_DONGLE, PID_DONGLE = 0x3554, 0xFA09
LED_LEN = 128
N_MODES = 20                      # LedOpt1..20 in KB.ini
PAL_LEN = (N_MODES + 1) * 21      # what OemDrv writes
MATRIX_LEN = 128 * 4              # MatrixLen=128 slots x 4 bytes, per layer
MACRO_LEN = 512                   # one macro page

# (hw id, name, has_speed, has_color)   — from KB.ini LedOptN + text.xml
MODES = {
    1: ("fixed",             False, True),
    2: ("respire",           True,  True),
    3: ("rainbow",           True,  False),
    4: ("flash-away",        True,  True),
    5: ("raindrops",         True,  True),
    6: ("rainbow-wheel",     True,  True),
    7: ("ripples",           True,  True),
    8: ("stars",             True,  True),
    9: ("shadow",            True,  True),
    10: ("snake",            True,  True),
    11: ("neon",             True,  True),
    12: ("reaction",         True,  True),
    13: ("sine-wave",        True,  True),
    14: ("scan",             True,  True),
    15: ("windmill",         True,  False),
    16: ("waterfall",        True,  False),
    17: ("blossom",          True,  False),
    18: ("storm",            True,  True),
}
OFF, CUSTOM = 0, 21
COLORS = ["red", "green", "blue", "yellow", "magenta", "cyan", "white", "rainbow"]
BY_NAME = {v[0]: k for k, v in MODES.items()}


class DeviceError(Exception):
    pass


def _hidraw_nodes():
    for d in sorted(glob.glob("/sys/class/hidraw/hidraw*")):
        try:
            ue = open(d + "/device/uevent").read().upper()
            rd = open(d + "/device/report_descriptor", "rb").read()
        except OSError:
            continue
        yield "/dev/" + os.path.basename(d), ue, rd


def _hid_id(vid, pid):
    return f"{vid:08X}:{pid:08X}"


def activity_nodes():
    """hidraw nodes that carry the keyboard's key reports (used only to notice typing)."""
    ids = (_hid_id(VID_DONGLE, PID_DONGLE), _hid_id(VID_WIRED, PID_WIRED))
    return [path for path, ue, _ in _hidraw_nodes() if any(i in ue for i in ids)]


class Dongle:
    """2.4G receiver — CDev3632 protocol."""
    kind = "2.4G dongle"
    RID = 0x13

    def __init__(self, path):
        self.path = path
        self.fd = os.open(path, os.O_RDWR)

    @classmethod
    def find(cls):
        for path, ue, rd in _hidraw_nodes():
            # vendor collection: Usage Page 0xFF02, Report ID 0x13
            if _hid_id(VID_DONGLE, PID_DONGLE) in ue and b"\x06\x02\xff" in rd and b"\x85\x13" in rd:
                return cls(path)

    def _pkt(self, b1, b2, b3, b4, data=b""):
        b = bytearray(20)
        b[0:5] = bytes([self.RID, b1, b2, b3, b4])
        b[5:5 + len(data)] = data
        b[19] = sum(b[:19]) & 0xFF
        return bytes(b)

    def _drain(self):
        while select.select([self.fd], [], [], 0)[0]:
            os.read(self.fd, 64)

    def _recv(self, cmd, timeout):
        end = time.time() + timeout
        while time.time() < end:
            if not select.select([self.fd], [], [], max(0, end - time.time()))[0]:
                break
            p = os.read(self.fd, 64)
            if len(p) >= 20 and p[0] == self.RID and (p[1] & 0x7F) == cmd:
                return p
        return None

    def read(self, cmd, flag=0, retries=3):
        with device_lock():
            return self._read(cmd, flag, retries)

    def _read(self, cmd, flag=0, retries=3):
        for _ in range(retries):
            self._drain()
            os.write(self.fd, self._pkt(cmd, 1, 0, flag << 4))
            chunks, total = {}, None
            while True:
                p = self._recv(cmd, 1.0)
                if p is None:
                    break
                if p[1] & 0x80 or p[2] & 0x80:
                    break                    # device reported CRC/err -> resend
                total = p[2] & 0x7F
                chunks[p[3]] = p[5:5 + min(p[4] & 0x0F, 14)]
                if len(chunks) >= total:
                    return b"".join(chunks[i] for i in range(total))
        raise DeviceError(f"read cmd 0x{cmd:02x} failed (keyboard asleep or off?)")

    def write(self, cmd, data, flag=0):
        with device_lock():
            self._write(cmd, data, flag)

    def _write(self, cmd, data, flag=0):
        n = (len(data) + 13) // 14
        for i in range(n):
            chunk = data[i * 14:(i + 1) * 14]
            for _ in range(5):
                self._drain()
                os.write(self.fd, self._pkt(cmd, n, i, (flag << 4) | len(chunk), chunk))
                p = self._recv(cmd, 1.0)
                if p and not (p[2] & 0x80) and p[3] == i:
                    break
            else:
                raise DeviceError(f"write cmd 0x{cmd:02x} packet {i}/{n} not acknowledged")
            time.sleep(0.01)

    def version(self):
        return self.read(0x07)[0]

    def battery(self):
        """Read 0x4A -> [percent, flags]; flags 0x10 = charging (cable in), 0x01 = on battery.
        Found by probing; the vendor driver doesn't read it for this keyboard (ShowPower=0)."""
        d = self.read(0x4A)
        return {"percent": min(100, d[0]), "charging": bool(d[1] & 0x10), "raw": d[:2].hex()}

    get_led = lambda s: s.read(0x44)
    set_led = lambda s, d: s.write(0x04, d)
    get_palette = lambda s: s.read(0x49)
    set_palette = lambda s, d: s.write(0x09, d)
    get_matrix = lambda s, layer: s.read(0x41, layer)
    set_matrix = lambda s, layer, d: s.write(0x01, d, layer)
    get_macros = lambda s: s.read(0x43, 0)           # page 0 (512 bytes)
    set_macros = lambda s, d: s.write(0x03, d, 0)


class Wired:
    """USB cable — CDevG5KB protocol, feature report 0x06 (Fw=24). Untested on hardware."""
    kind = "USB wired"
    RID = 0x06
    SIZE = 0x208

    def __init__(self, path):
        import fcntl
        self.fcntl = fcntl
        self.path = path
        self.fd = os.open(path, os.O_RDWR)

    @classmethod
    def find(cls):
        for path, ue, rd in _hidraw_nodes():
            if _hid_id(VID_WIRED, PID_WIRED) in ue and b"\x06\x00\xff" in rd and b"\x85\x06" in rd:
                return cls(path)

    def _ioc(self, nr):        # HIDIOCSFEATURE / HIDIOCGFEATURE
        return (3 << 30) | (self.SIZE << 16) | (ord("H") << 8) | nr

    def _xfer(self, cmd, arg, payload, total_len, nchunks, idx, read):
        b = bytearray(self.SIZE)
        b[0:8] = bytes([self.RID, cmd, arg, 0, nchunks, idx, total_len & 0xFF, total_len >> 8])
        b[8:8 + len(payload)] = payload
        for _ in range(3):
            try:
                self.fcntl.ioctl(self.fd, self._ioc(0x06), bytes(b))
                break
            except OSError:
                time.sleep(0.07)
        else:
            raise DeviceError(f"SetFeature cmd 0x{cmd:02x} failed")
        if read:
            time.sleep(0.02)
            r = bytearray(self.SIZE)
            r[0] = self.RID
            self.fcntl.ioctl(self.fd, self._ioc(0x07), r)
            return bytes(r[8:8 + total_len])

    def _access(self, cmd, data_or_len, read, arg=0):
        size = data_or_len if read else len(data_or_len)
        n = (size + 511) // 512
        out = b""
        for i in range(n):
            ln = min(512, size - i * 512)
            payload = b"" if read else data_or_len[i * 512:i * 512 + ln]
            r = self._xfer(cmd | (0x80 if read else 0), arg, payload, ln, n, i, read)
            if read:
                out += r
            time.sleep(0.02)
        return out

    def version(self):
        return None

    def battery(self):
        return None          # on the cable the keyboard is powered (and charging) anyway

    get_led = lambda s: s._access(0x04, LED_LEN, True)
    set_led = lambda s, d: s._access(0x04, d, False)
    get_palette = lambda s: s._access(0x0A, PAL_LEN, True)
    set_palette = lambda s, d: s._access(0x0A, d, False)
    get_matrix = lambda s, layer: s._access(0x03, MATRIX_LEN, True, layer)
    set_matrix = lambda s, layer, d: s._access(0x03, d, False, layer)
    get_macros = lambda s: s._access(0x05, MACRO_LEN, True)
    set_macros = lambda s, d: s._access(0x05, d, False)


# ---------------------------------------------------------------- key remapping
# Physical key -> matrix slot (from Dev/kb/1/KB.ini [KEY], last field)
PHYS = {
    "esc": 0, "f1": 12, "f2": 18, "f3": 24, "f4": 30, "f5": 36, "f6": 42, "f7": 48,
    "f8": 54, "f9": 60, "f10": 66, "f11": 72, "f12": 78, "end": 88,
    "grave": 1, "1": 7, "2": 13, "3": 19, "4": 25, "5": 31, "6": 37, "7": 43, "8": 49,
    "9": 55, "0": 61, "minus": 67, "equal": 73, "backspace": 79, "delete": 85,
    "tab": 2, "q": 8, "w": 14, "e": 20, "r": 26, "t": 32, "y": 38, "u": 44, "i": 50,
    "o": 56, "p": 62, "lbracket": 68, "rbracket": 74, "backslash": 80, "pgup": 86,
    "capslock": 3, "a": 9, "s": 15, "d": 21, "f": 27, "g": 33, "h": 39, "j": 45,
    "k": 51, "l": 57, "semicolon": 63, "quote": 69, "enter": 81,
    "lshift": 4, "z": 10, "x": 16, "c": 22, "v": 28, "b": 34, "n": 40, "m": 46,
    "comma": 52, "period": 58, "slash": 64, "rshift": 70, "up": 82,
    "lctrl": 5, "lwin": 11, "lalt": 17, "space": 35, "fn": 53, "rctrl": 59,
    "left": 77, "down": 83, "right": 89, "pgdn": 87,
}
PHYS_ORDER = sorted(PHYS, key=lambda k: PHYS[k])
ALIASES = {"`": "grave", "-": "minus", "=": "equal", "[": "lbracket", "]": "rbracket",
           "\\": "backslash", ";": "semicolon", "'": "quote", ",": "comma", ".": "period",
           "/": "slash", "escape": "esc", "return": "enter", "bksp": "backspace", "del": "delete",
           "caps": "capslock", "pageup": "pgup", "pagedown": "pgdn", "ctrl": "lctrl",
           "shift": "lshift", "alt": "lalt", "win": "lwin", "super": "lwin", "gui": "lwin",
           "meta": "lwin", "lgui": "lwin", "rgui": "rwin", "lsuper": "lwin", "rsuper": "rwin",
           "ins": "insert", "prtsc": "printscreen", "print": "printscreen", "menu": "app",
           "esc": "esc", "spacebar": "space"}

MODS = {"lctrl": 0x01, "lshift": 0x02, "lalt": 0x04, "lwin": 0x08,
        "rctrl": 0x10, "rshift": 0x20, "ralt": 0x40, "rwin": 0x80}

HID = {"esc": 0x29, "enter": 0x28, "backspace": 0x2A, "tab": 0x2B, "space": 0x2C,
       "minus": 0x2D, "equal": 0x2E, "lbracket": 0x2F, "rbracket": 0x30, "backslash": 0x31,
       "semicolon": 0x33, "quote": 0x34, "grave": 0x35, "comma": 0x36, "period": 0x37,
       "slash": 0x38, "capslock": 0x39, "printscreen": 0x46, "scrolllock": 0x47, "pause": 0x48,
       "insert": 0x49, "home": 0x4A, "pgup": 0x4B, "delete": 0x4C, "end": 0x4D, "pgdn": 0x4E,
       "right": 0x4F, "left": 0x50, "down": 0x51, "up": 0x52, "numlock": 0x53,
       "kp_slash": 0x54, "kp_asterisk": 0x55, "kp_minus": 0x56, "kp_plus": 0x57,
       "kp_enter": 0x58, "kp_period": 0x63, "app": 0x65, "nonus_backslash": 0x64}
HID.update({chr(ord("a") + i): 0x04 + i for i in range(26)})
HID.update({str((i + 1) % 10): 0x1E + i for i in range(10)})
HID.update({f"f{i}": 0x3A + i - 1 for i in range(1, 13)})
HID.update({f"f{i}": 0x68 + i - 13 for i in range(13, 25)})
HID.update({f"kp_{(i + 1) % 10}": 0x59 + i for i in range(10)})
HID_NAME = {v: k for k, v in HID.items()}

MEDIA = {"play": 0x0CD, "stop": 0x0B7, "next": 0x0B5, "prev": 0x0B6, "mute": 0x0E2,
         "volup": 0x0E9, "voldown": 0x0EA, "mail": 0x18A, "calc": 0x192, "mycomputer": 0x194,
         "browser": 0x223, "www_back": 0x224, "www_forward": 0x225, "www_stop": 0x226,
         "www_refresh": 0x227, "www_favorites": 0x22A, "media_player": 0x183,
         "brightness_up": 0x06F, "brightness_down": 0x070}
MEDIA_NAME = {v: k for k, v in MEDIA.items()}
MACRO_MODES = {"times": 1, "hold": 2, "toggle": 4}   # cycle N times / until released / until any key
MACRO_MODE_NAME = {v: k for k, v in MACRO_MODES.items()}
LAYERS = {"base": 0, "fn": 1}


def norm(name):
    n = name.strip().lower()
    return ALIASES.get(n, n)


def phys_slot(name):
    n = norm(name)
    if n not in PHYS:
        raise DeviceError(f"unknown physical key {name!r}; see `aula-f75 keys`")
    return PHYS[n]


def encode_action(spec):
    """Text action -> 4 hardware bytes."""
    s = spec.strip().lower()
    if s in ("disable", "none", "off"):
        return bytes(4)
    if s.startswith("macro:"):
        parts = s.split(":")
        mid = int(parts[1])
        mode = MACRO_MODES.get(parts[2], None) if len(parts) > 2 else 1
        if mode is None:
            raise DeviceError(f"macro mode must be one of {', '.join(MACRO_MODES)}")
        count = int(parts[3]) if len(parts) > 3 else 1
        if not (0 <= mid < 64 and 1 <= count <= 255):
            raise DeviceError("macro id 0-63, count 1-255")
        return bytes([3, mode, count if mode == 1 else 1, mid])
    if norm(s) in MEDIA:
        u = MEDIA[norm(s)]
        return bytes([2, 0, u >> 8, u & 0xFF])
    mods, keys = 0, []
    for p in s.split("+"):
        p = norm(p)
        if p in MODS:
            mods |= MODS[p]
        elif p in HID:
            keys.append(HID[p])
        elif p.startswith("0x"):
            keys.append(int(p, 16))
        else:
            raise DeviceError(f"unknown key {p!r} in {spec!r}; see `aula-f75 keynames`")
    if len(keys) > 2:
        raise DeviceError("at most two non-modifier keys per binding")
    keys = keys + [0] * (2 - len(keys))
    return bytes([0, mods, keys[1], keys[0]])


def decode_action(b):
    t = b[0]
    if b == bytes(4):
        return "disabled"
    if t == 0:
        parts = [n for n, bit in MODS.items() if b[1] & bit]
        parts += [HID_NAME.get(k, f"0x{k:02x}") for k in (b[3], b[2]) if k]
        return "+".join(parts) or "none"
    if t == 2:
        u = (b[2] << 8) | b[3]
        return MEDIA_NAME.get(u, f"media:0x{u:03x}")
    if t == 3:
        m = MACRO_MODE_NAME.get(b[1], str(b[1]))
        return f"macro:{b[3]}:{m}" + (f":{b[2]}" if b[1] == 1 else "")
    if t == 0x0D:
        return "fn"
    return f"special({b.hex(' ')})"


def read_layer(dev, layer):
    m = bytearray(dev.get_matrix(layer))
    if len(m) < 90 * 4:
        raise DeviceError(f"key map read returned only {len(m)} bytes")
    return m + bytearray(MATRIX_LEN - len(m)) if len(m) < MATRIX_LEN else m[:MATRIX_LEN]


def cmd_keys(dev, a):
    layer = LAYERS[a.layer]
    m = read_layer(dev, layer)
    print(f"{a.layer} layer:")
    for k in PHYS_ORDER:
        i = PHYS[k]
        print(f"  {k:10s} -> {decode_action(bytes(m[i*4:i*4+4]))}")


def cmd_remap(dev, a):
    layer = LAYERS[a.layer]
    slot = phys_slot(a.key)
    if a.action.lower() == "default":
        import json
        fk = json.load(open(os.path.join(HERE, "factory-keys.json")))
        code = bytes.fromhex(fk[f"matrix{layer}"])[slot*4:slot*4+4]
    else:
        code = encode_action(a.action)
    if layer == 0 and slot == PHYS["fn"] and not a.force:
        raise DeviceError("remapping FN removes access to the Fn layer; add --force if you really want that")
    m = read_layer(dev, layer)
    old = bytes(m[slot*4:slot*4+4])
    m[slot*4:slot*4+4] = code
    dev.set_matrix(layer, bytes(m))
    time.sleep(0.1)
    if bytes(read_layer(dev, layer)[slot*4:slot*4+4]) != code:
        raise DeviceError("keyboard did not keep the new binding")
    print(f"{a.layer}:{norm(a.key)}  {decode_action(old)}  ->  {decode_action(code)}")


def cmd_reset_keys(dev, a):
    import json
    fk = json.load(open(os.path.join(HERE, "factory-keys.json")))
    for layer in (0, 1):
        d = bytes.fromhex(fk[f"matrix{layer}"])
        dev.set_matrix(layer, d + bytes(MATRIX_LEN - len(d)))
    print("base and fn layers restored from factory-keys.json")


def cmd_keynames(_dev, _a):
    print("modifiers:", ", ".join(MODS))
    print("keys     :", ", ".join(sorted(HID, key=lambda k: HID[k])))
    print("media    :", ", ".join(MEDIA))
    print("other    : disable, default, macro:ID[:times[:N]|:hold|:toggle]")
    print("combos   : ctrl+c, ctrl+shift+t, lwin+e  (up to 2 keys + any modifiers)")


# ---------------------------------------------------------------------- macros
# Buffer: N x [u16 addr, u16 size] then at addr: [nameLen][UTF-16 name][events]
# event: [type<<4 | 0x80 if release | delay>>16, delay>>8, delay, code]   (type 0 = key)
MOD_HID = {"lctrl": 0xE0, "lshift": 0xE1, "lalt": 0xE2, "lwin": 0xE3,
           "rctrl": 0xE4, "rshift": 0xE5, "ralt": 0xE6, "rwin": 0xE7}
HID_ALL = dict(HID, **MOD_HID)
HID_ALL_NAME = {v: k for k, v in HID_ALL.items()}
SHIFTED = {'!': '1', '@': '2', '#': '3', '$': '4', '%': '5', '^': '6', '&': '7', '*': '8',
           '(': '9', ')': '0', '_': 'minus', '+': 'equal', '{': 'lbracket', '}': 'rbracket',
           '|': 'backslash', ':': 'semicolon', '"': 'quote', '~': 'grave', '<': 'comma',
           '>': 'period', '?': 'slash'}
PLAIN = {' ': 'space', '-': 'minus', '=': 'equal', '[': 'lbracket', ']': 'rbracket',
         '\\': 'backslash', ';': 'semicolon', "'": 'quote', '`': 'grave', ',': 'comma',
         '.': 'period', '/': 'slash', '\n': 'enter', '\t': 'tab'}


def parse_macros(buf):
    macros = []
    if len(buf) < 4:
        return macros
    first = buf[0] | buf[1] << 8
    if first == 0 or first % 4 or first > len(buf):
        return macros
    for i in range(first // 4):
        addr = buf[i*4] | buf[i*4+1] << 8
        size = buf[i*4+2] | buf[i*4+3] << 8
        if addr == 0 or addr + size > len(buf):
            break
        nl = buf[addr]
        name = bytes(buf[addr+1:addr+1+nl]).decode("utf-16-le", "replace")
        ev = bytes(buf[addr+1+nl:addr+size])
        macros.append((name, [ev[j:j+4] for j in range(0, len(ev) - 3, 4)]))
    return macros


def build_macros(macros):
    n = len(macros)
    head, body = bytearray(), bytearray()
    pos = 4 * n
    for name, events in macros:
        nm = name[:30].encode("utf-16-le")
        blob = bytes([len(nm)]) + nm + b"".join(events)
        head += bytes([pos & 0xFF, pos >> 8, len(blob) & 0xFF, len(blob) >> 8])
        body += blob
        pos += len(blob)
    out = head + body
    if len(out) > MACRO_LEN:
        raise DeviceError(f"macros need {len(out)} bytes; the keyboard holds {MACRO_LEN}")
    return bytes(out + bytes(MACRO_LEN - len(out)))


EVENT_TYPE = 0x00   # type 0 (like the factory macro) is what the F75 plays; type 1 (--type1) is stored but never plays


def ev(code, release, delay):
    delay = max(0, min(delay, 0xFFFFF))
    return bytes([EVENT_TYPE | (delay >> 16) | (0x80 if release else 0), (delay >> 8) & 0xFF, delay & 0xFF, code])


def compile_macro(spec, gap):
    """Tokens: ctrl+c (tap combo), +shift (hold), -shift (release), 200ms (wait),
    "typed text" (quoted). Delay is attached after the preceding event."""
    events = []

    def add(code, rel):
        events.append(bytearray(ev(code, rel, gap)))

    def tap(names):
        codes = []
        for n in names:
            n = norm(n)
            if n not in HID_ALL:
                raise DeviceError(f"unknown key {n!r} in macro")
            codes.append(HID_ALL[n])
        for c in codes:
            add(c, False)
        for c in reversed(codes):
            add(c, True)

    import re
    for m in re.finditer(r'"([^"]*)"|(\S+)', spec):
        quoted = m.group(1) is not None
        tok = m.group(1) if quoted else m.group(2)
        if not quoted and tok.endswith("ms") and tok[:-2].isdigit():
            if not events:
                raise DeviceError("a wait cannot be the first macro item")
            d = int(tok[:-2])
            e = events[-1]
            e[0] = (e[0] & 0xF0) | ((d >> 16) & 0x0F); e[1] = (d >> 8) & 0xFF; e[2] = d & 0xFF
        elif quoted:
            for ch in tok:
                if ch.isupper():
                    tap(["lshift", ch.lower()])
                elif ch in SHIFTED:
                    tap(["lshift", SHIFTED[ch]])
                elif ch in PLAIN:
                    tap([PLAIN[ch]])
                elif ch.isalnum():
                    tap([ch])
                else:
                    raise DeviceError(f"can't type {ch!r}")
        elif tok[0] in "+-" and len(tok) > 1:
            n = norm(tok[1:])
            if n not in HID_ALL:
                raise DeviceError(f"unknown key {n!r} in macro")
            add(HID_ALL[n], tok[0] == "-")
        else:
            tap(tok.split("+"))
    if not events:
        raise DeviceError("empty macro")
    return [bytes(e) for e in events]


def describe_events(events):
    out = []
    for e in events:
        d = ((e[0] & 0x0F) << 16) | (e[1] << 8) | e[2]
        name = HID_ALL_NAME.get(e[3], f"0x{e[3]:02x}") if (e[0] & 0x70) in (0x00, 0x10) else f"t{(e[0]>>4)&7}:{e[3]}"
        out.append(f"{'-' if e[0] & 0x80 else '+'}{name}" + (f" {d}ms" if d else ""))
    return " ".join(out)


def cmd_macro(dev, a):
    macros = parse_macros(dev.get_macros())
    if a.op == "list":
        if not macros:
            print("no macros stored")
        for i, (name, evs) in enumerate(macros):
            print(f"[{i}] {name!r}: {describe_events(evs)}")
        return
    if a.op == "set":
        global EVENT_TYPE
        if a.type1:
            EVENT_TYPE = 0x10
        if a.id > len(macros):
            raise DeviceError(f"next free macro id is {len(macros)}")
        events = compile_macro(a.spec, a.gap)
        entry = (a.name or f"m{a.id}", events)
        if a.id == len(macros):
            macros.append(entry)
        else:
            macros[a.id] = entry
    elif a.op == "delete":
        if a.id != len(macros) - 1:
            raise DeviceError(f"only the last macro (id {len(macros)-1}) can be deleted, "
                              "so other ids keep pointing at the right macro")
        macros.pop()
    buf = build_macros(macros)
    dev.set_macros(buf)
    time.sleep(0.1)
    if dev.get_macros()[:len(buf)] != buf:
        raise DeviceError("macro memory read-back did not match")
    print(f"stored {len(macros)} macro(s)")
    if a.op == "set":
        print(f"[{a.id}] {describe_events(events)}")
        print(f"bind it with e.g.: aula-f75 remap f12 macro:{a.id} --layer fn")


HERE = os.path.dirname(os.path.realpath(__file__))


def open_device():
    for cls in (Wired, Dongle):
        try:
            dev = cls.find()
        except PermissionError:
            sys.exit("Permission denied on /dev/hidraw*. Install the udev rule (see README) and replug.")
        if dev:
            return dev
    sys.exit("AULA F75 not found (looked for 258a:010c wired and 3554:fa09 dongle).")


def mode_id(s):
    s = s.lower()
    if s.isdigit():
        v = int(s)
        if v in MODES or v in (OFF, CUSTOM):
            return v
    if s == "off":
        return OFF
    if s in ("custom", "self-define"):
        return CUSTOM
    if s in BY_NAME:
        return BY_NAME[s]
    raise argparse.ArgumentTypeError(f"unknown mode {s!r}; see `aula-f75 modes`")


def color_id(s):
    s = s.lower()
    if s.isdigit() and 0 <= int(s) <= 7:
        return int(s)
    if s in COLORS:
        return COLORS.index(s)
    raise argparse.ArgumentTypeError(f"color must be 0-7 or one of {', '.join(COLORS)}")


def check_led(buf):
    if len(buf) < LED_LEN or buf[126:128] != b"\x5a\xa5":
        raise DeviceError("LED profile from keyboard is invalid (missing 5A A5 magic); refusing to write")


def mode_name(m):
    return "off" if m == OFF else "custom" if m == CUSTOM else MODES.get(m, (f"mode{m}",))[0]


def decode(buf, m):
    b, sc = buf[0x3A + 2 * (m - 1)], buf[0x3B + 2 * (m - 1)]
    return b, sc >> 4, sc & 0x0F


SLEEP_OFF = 0x18
SLEEP_CHOICES = [60, 90, 120, 180, 240, 300, 600, 900, 1200]   # seconds, from KB.ini SleepUI (HW = s // 30)


def sleep_seconds(led):
    return led[SLEEP_OFF] * 30          # 0 = never


def fmt_sleep(sec):
    if not sec:
        return "never"
    return f"{sec // 60} min" + (f" {sec % 60} s" if sec % 60 else "") if sec >= 60 else f"{sec} s"


def cmd_sleep(dev, a):
    led = bytearray(dev.get_led())
    check_led(led)
    if a.minutes is None:
        print(f"sleep after: {fmt_sleep(sleep_seconds(led))}")
        return
    if a.minutes == "never":
        led[SLEEP_OFF] = 0
    else:
        sec = round(float(a.minutes) * 60)
        if sec not in SLEEP_CHOICES:
            raise DeviceError("choose one of: " + ", ".join(f"{s / 60:g}" for s in SLEEP_CHOICES) + " (minutes) or 'never'")
        led[SLEEP_OFF] = sec // 30
    dev.set_led(bytes(led))
    print(f"sleep after: {fmt_sleep(sleep_seconds(led))}")


def lighting_now(led):
    m = led[0x0A]
    return m, (decode(led, m)[0] if m in MODES else 0)


def cmd_battery(dev, a):
    import battery_health as H
    bat = dev.battery()
    if not bat:
        print("battery    : not reported over this connection")
    else:
        print(f"battery    : {bat['percent']}%" + (" (charging)" if bat["charging"] else ""))
    e = H.estimate()
    if e["health"] is None:
        seen = e["observedDischarge"] + e["observedCharge"]
        print(f"health     : collecting data ({seen:g}% of {e['needed']}% change seen, {e['samples']} readings)")
        print("             run `aula-f75 battery-log` (installed as a user service) to collect it")
    else:
        print(f"health     : ~{e['health']}% (likely {e['low']}-{e['high']}%, {e['confidence']} estimate)")


def cmd_battery_log(_dev, a):
    """Background logger: reads the battery only right after the keyboard was used, so it never
    keeps an idle keyboard awake (any read resets the keyboard's sleep timer)."""
    import battery_health as H
    w = H.ActivityWatcher(activity_nodes)
    w.start()
    base = H.last_awake()
    last = 0.0
    print(f"logging to {H.LOG_PATH} (every {a.interval}s of use)", flush=True)
    while True:
        time.sleep(10)
        if w.idle_for() > 8 or time.time() - last < a.interval:
            continue
        dev = None
        try:
            dev = open_device()
            led = dev.get_led()
            bat = dev.battery()
        except (DeviceError, OSError, SystemExit) as e:
            print(f"reading skipped: {e}", file=sys.stderr, flush=True)
            continue
        finally:
            if dev is not None:
                try:
                    os.close(dev.fd)
                except OSError:
                    pass
        w.sleep_s = sleep_seconds(led) or 3600
        if not bat:
            continue
        mode, bri = lighting_now(led)
        H.append({"t": round(time.time()), "pct": bat["percent"], "chg": bat["charging"],
                  "mode": mode, "bri": bri, "awake": round(base + w.awake_seconds())})
        last = time.time()


def cmd_info(dev, a):
    led = dev.get_led()
    check_led(led)
    cur = led[0x0A]
    v = dev.version()
    print(f"connection : {dev.kind} ({dev.path})" + (f", fw byte 0x{v:02x}" if v is not None else ""))
    try:
        bat = dev.battery()
    except DeviceError:
        bat = None
    if bat:
        print(f"battery    : {bat['percent']}%" + (" (charging)" if bat["charging"] else ""))
    print(f"sleep after: {fmt_sleep(sleep_seconds(led))}")
    print(f"mode       : {cur} ({mode_name(cur)})")
    if cur in MODES:
        b, s, c = decode(led, cur)
        print(f"brightness : {b}/9\nspeed      : {s}/4\ncolor      : {c} ({COLORS[c] if c < 8 else '?'})")
    if a.verbose:
        print("raw led    :", led.hex(" "))


def cmd_set(dev, a):
    led = bytearray(dev.get_led())
    check_led(led)
    m = a.mode
    led[0x0A] = m
    if m in MODES:
        bi, si = 0x3A + 2 * (m - 1), 0x3B + 2 * (m - 1)
        b, s, c = led[bi], led[si] >> 4, led[si] & 0x0F
        if a.brightness is not None:
            b = a.brightness
        if a.speed is not None:
            s = a.speed
        if a.color is not None:
            if not MODES[m][2] and a.color != 7:
                print(f"note: {mode_name(m)} has no color option; ignoring --color", file=sys.stderr)
            else:
                c = a.color
        led[bi], led[si] = b, (s << 4) | c
    elif any(x is not None for x in (a.brightness, a.speed, a.color)):
        print("note: brightness/speed/color only apply to effect modes 1-18", file=sys.stderr)
    dev.set_led(bytes(led))
    time.sleep(0.1)
    if dev.get_led()[0x0A] != m:
        raise DeviceError("keyboard did not accept the new mode")
    print(f"set mode {m} ({mode_name(m)})")


def cmd_palette(dev, a):
    tab = bytearray(dev.get_palette())
    if len(tab) < PAL_LEN:
        raise DeviceError(f"palette table too short ({len(tab)} bytes)")
    tab = tab[:PAL_LEN]
    m = a.mode
    if m not in MODES:
        raise DeviceError("palette exists only for modes 1-18")
    if a.rgb is None:
        for i in range(7):
            o = m * 21 + i * 3
            print(f"{i} {COLORS[i]:8s} #{tab[o:o+3].hex()}")
        return
    rgb = bytes.fromhex(a.rgb.lstrip("#"))
    if len(rgb) != 3:
        raise DeviceError("rgb must be RRGGBB")
    o = m * 21 + a.slot * 3
    tab[o:o + 3] = rgb
    dev.set_palette(bytes(tab))
    print(f"mode {mode_name(m)} color slot {a.slot} = #{rgb.hex()}  (select it with: set {mode_name(m)} -c {a.slot})")


def cmd_backup(dev, a):
    import json
    led, pal = dev.get_led(), dev.get_palette()
    check_led(led)
    data = {"format": "aula-f75/2", "led": led.hex(), "palette": pal.hex(),
            "matrix0": bytes(read_layer(dev, 0)).hex(), "matrix1": bytes(read_layer(dev, 1)).hex(),
            "macros": dev.get_macros().hex()}
    with open(a.file, "w") as f:
        json.dump(data, f, indent=1)
    print(f"saved lighting, palette, key map (base+fn) and macros to {a.file}")


def cmd_restore(dev, a):
    import json
    raw = open(a.file, "rb").read()
    if raw[:4] == b"AF75":                                  # v1: lighting only
        n = int.from_bytes(raw[4:6], "little"); led = raw[6:6 + n]
        p = 6 + n; m = int.from_bytes(raw[p:p + 2], "little"); pal = raw[p + 2:p + 2 + m]
        data = {"led": led.hex(), "palette": pal.hex()}
    else:
        data = json.loads(raw)
        if data.get("format") != "aula-f75/2":
            raise DeviceError("not an aula-f75 backup")
    led = bytes.fromhex(data["led"]); check_led(led)
    dev.set_led(led)
    pal = bytes.fromhex(data["palette"])
    if len(pal) >= PAL_LEN:
        dev.set_palette(pal[:PAL_LEN])
    done = ["lighting"]
    for layer in (0, 1):
        if f"matrix{layer}" in data:
            dev.set_matrix(layer, bytes.fromhex(data[f"matrix{layer}"]))
            done.append(f"{'base' if layer == 0 else 'fn'} keys")
    if "macros" in data:
        dev.set_macros(bytes.fromhex(data["macros"])[:MACRO_LEN])
        done.append("macros")
    print("restored " + ", ".join(done))


def cmd_modes(_dev, _a):
    print(" id  name            speed  color")
    print("  0  off")
    for k, (n, s, c) in MODES.items():
        print(f"{k:3d}  {n:15s} {'yes' if s else '-':6s} {'yes' if c else 'rainbow only'}")
    print(" 21  custom          (per-key colours; set in Windows app)")
    print("colors: " + ", ".join(f"{i}={c}" for i, c in enumerate(COLORS)))


def main():
    ap = argparse.ArgumentParser(prog="aula-f75", description="AULA F75 lighting control for Linux")
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("info", help="show connection and current lighting"); p.add_argument("-v", "--verbose", action="store_true")
    sp.add_parser("modes", help="list lighting modes and colours")
    sp.add_parser("battery", help="show battery level and the estimated battery health")
    p = sp.add_parser("battery-log", help="run the background battery logger (for the health estimate)")
    p.add_argument("--interval", type=int, default=600, help="seconds between readings while in use (default 600)")
    p = sp.add_parser("sleep", help="show or set how long the keyboard waits before sleeping")
    p.add_argument("minutes", nargs="?", help="1, 1.5, 2, 3, 4, 5, 10, 15, 20 or 'never'")
    p = sp.add_parser("set", help="set lighting mode (and optionally brightness/speed/color)")
    p.add_argument("mode", type=mode_id)
    p.add_argument("-b", "--brightness", type=int, choices=range(10), metavar="0-9")
    p.add_argument("-s", "--speed", type=int, choices=range(5), metavar="0-4")
    p.add_argument("-c", "--color", type=color_id, metavar="COLOR")
    p = sp.add_parser("palette", help="show or edit a mode's 7-colour palette")
    p.add_argument("mode", type=mode_id)
    p.add_argument("slot", type=int, nargs="?", choices=range(7), metavar="SLOT(0-6)")
    p.add_argument("rgb", nargs="?", metavar="RRGGBB")
    p = sp.add_parser("backup", help="save lighting, key map and macros to a file"); p.add_argument("file")
    p = sp.add_parser("restore", help="write a saved backup back to the keyboard"); p.add_argument("file")
    p = sp.add_parser("keys", help="show what every key does")
    p.add_argument("--layer", choices=LAYERS, default="base")
    p = sp.add_parser("remap", help="change what a key does",
                      description="ACTION: a key (b, f5, esc), combo (ctrl+c, lwin+e), media key "
                                  "(play, volup, mute), 'disable', 'default', or macro:ID[:times[:N]|:hold|:toggle]")
    p.add_argument("key", help="physical key, e.g. capslock, f12, rctrl")
    p.add_argument("action")
    p.add_argument("--layer", choices=LAYERS, default="base", help="base (default) or fn (key held with Fn)")
    p.add_argument("--force", action="store_true", help=argparse.SUPPRESS)
    sp.add_parser("reset-keys", help="restore base and fn layers to the factory key map")
    sp.add_parser("keynames", help="list names usable as remap targets")
    p = sp.add_parser("macro", help="list / create / delete on-board macros")
    msp = p.add_subparsers(dest="op", required=True)
    msp.add_parser("list")
    q = msp.add_parser("set", help='e.g. macro set 1 \'ctrl+c 50ms ctrl+v\' or macro set 2 \'"hello" enter\'')
    q.add_argument("id", type=int)
    q.add_argument("spec")
    q.add_argument("--name")
    q.add_argument("--gap", type=int, default=15, help="ms between events (default 15)")
    q.add_argument("--type1", action="store_true", help="encode key events as type 1 (stored, but the F75 doesn't play them)")
    q = msp.add_parser("delete"); q.add_argument("id", type=int)
    a = ap.parse_args()
    if a.cmd == "palette" and (a.slot is None) != (a.rgb is None):
        ap.error("palette needs both SLOT and RRGGBB, or neither")
    dev = None if a.cmd in ("modes", "keynames", "battery-log") else open_device()
    try:
        globals()["cmd_" + a.cmd.replace("-", "_")](dev, a)
    except DeviceError as e:
        sys.exit(f"error: {e}")


if __name__ == "__main__":
    main()
