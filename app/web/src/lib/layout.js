// Vector geometry of the AULA F75 (75% layout + knob), in key units.
// Key names match PHYS in aula_f75.py.
const L = (k, w, main, shift) => ({ k, w, main, shift });
const gap = (w) => ({ gap: w });
const letters = (s) => [...s].map((c) => L(c, 1, c.toUpperCase()));

const ROWS = [
  { y: 0, keys: [L("esc", 1, "Esc"), gap(0.5), ...[1, 2, 3, 4].map((n) => L("f" + n, 1, "F" + n)), gap(0.5),
    ...[5, 6, 7, 8].map((n) => L("f" + n, 1, "F" + n)), gap(0.5),
    ...[9, 10, 11, 12].map((n) => L("f" + n, 1, "F" + n)), gap(0.5), L("wheel", 1, "")] },
  { y: 1.25, keys: [L("grave", 1, "`", "~"), ...["1!", "2@", "3#", "4$", "5%", "6^", "7&", "8*", "9(", "0)"].map((p) => L(p[0], 1, p[0], p[1])),
    L("minus", 1, "-", "_"), L("equal", 1, "=", "+"), L("backspace", 2, "Backspace"), L("delete", 1, "Del")] },
  { y: 2.25, keys: [L("tab", 1.5, "Tab"), ...letters("qwertyuiop"), L("lbracket", 1, "[", "{"), L("rbracket", 1, "]", "}"),
    L("backslash", 1.5, "\\", "|"), L("pgup", 1, "PgUp")] },
  { y: 3.25, keys: [L("capslock", 1.75, "Caps Lock"), ...letters("asdfghjkl"), L("semicolon", 1, ";", ":"), L("quote", 1, "'", "\""),
    L("enter", 2.25, "Enter"), L("pgdn", 1, "PgDn")] },
  { y: 4.25, keys: [L("lshift", 2.25, "Shift"), ...letters("zxcvbnm"), L("comma", 1, ",", "<"), L("period", 1, ".", ">"),
    L("slash", 1, "/", "?"), L("rshift", 1.75, "Shift"), L("up", 1, "↑"), L("end", 1, "End")] },
  { y: 5.25, keys: [L("lctrl", 1.25, "Ctrl"), L("lwin", 1.25, "Win"), L("lalt", 1.25, "Alt"), L("space", 6.25, ""),
    L("fn", 1.25, "Fn"), L("rctrl", 1.25, "Ctrl"), gap(0.5), L("left", 1, "←"), L("down", 1, "↓"), L("right", 1, "→")] },
];
const ACCENT = new Set(["esc", "enter", "space", "up", "down", "left", "right"]);

export const U = 56;           // px per key unit (viewBox units)
const PAD = 0.5;               // case border, in units
const INSET = 2.5;             // half the gap between caps, px

export function buildLayout() {
  const keys = [];
  for (const row of ROWS) {
    let x = 0;
    for (const item of row.keys) {
      if (item.gap) { x += item.gap; continue; }
      keys.push({
        key: item.k, main: item.main, shift: item.shift, accent: ACCENT.has(item.k), knob: item.k === "wheel",
        x: (PAD + x) * U + INSET, y: (PAD + row.y) * U + INSET,
        w: item.w * U - 2 * INSET, h: U - 2 * INSET,
      });
      x += item.w;
    }
  }
  return {
    width: (16 + 2 * PAD) * U,
    height: (6.25 + 2 * PAD) * U,
    pad: PAD * U,
    keys: keys.filter((k) => !k.knob),
    knob: keys.find((k) => k.knob),
  };
}
