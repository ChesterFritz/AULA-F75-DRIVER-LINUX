export const MODE_LABEL = {
  fixed: "Fixed on", respire: "Breathing", rainbow: "Rainbow", "flash-away": "Flash away",
  raindrops: "Raindrops", "rainbow-wheel": "Rainbow wheel", ripples: "Ripples", stars: "Starlight",
  shadow: "Fading trail", snake: "Snake", neon: "Neon stream", reaction: "Reactive",
  "sine-wave": "Sine wave", scan: "Scanner", windmill: "Windmill", waterfall: "Waterfall",
  blossom: "Blossom", storm: "Storm",
};
export const MODE_HINT = {
  fixed: "Steady light on every key", respire: "Fades slowly in and out",
  rainbow: "Colours sweep across the board", "flash-away": "Keys flash and fade at random",
  raindrops: "Drops of light here and there", "rainbow-wheel": "Colours turn around the centre",
  ripples: "Rings spread out from keys", stars: "Keys twinkle on and off",
  shadow: "A trail follows your typing", snake: "A light snakes along the rows",
  neon: "The whole board shifts colour", reaction: "Keys light up when pressed",
  "sine-wave": "A wave rolls across", scan: "A bar sweeps side to side",
  windmill: "Blades of colour turn", waterfall: "Colours flow downwards",
  blossom: "Colour blooms from the centre", storm: "Sudden flashes, like lightning",
};

export const KEY_LABEL = {
  esc: "Esc", grave: "`", minus: "-", equal: "=", backspace: "Backspace", delete: "Delete", tab: "Tab",
  lbracket: "[", rbracket: "]", backslash: "\\", pgup: "Page Up", pgdn: "Page Down", capslock: "Caps Lock",
  semicolon: ";", quote: "'", enter: "Enter", lshift: "Left Shift", rshift: "Right Shift", comma: ",",
  period: ".", slash: "/", up: "Up", down: "Down", left: "Left", right: "Right", lctrl: "Left Ctrl",
  rctrl: "Right Ctrl", lwin: "Super", rwin: "Right Super", lalt: "Left Alt", ralt: "Right Alt", space: "Space",
  fn: "Fn", end: "End", home: "Home", insert: "Insert", printscreen: "Print Screen", scrolllock: "Scroll Lock",
  pause: "Pause", app: "Menu", numlock: "Num Lock", wheel: "Knob",
};
export const MEDIA_LABEL = {
  play: "Play / pause", stop: "Stop", next: "Next track", prev: "Previous track", mute: "Mute",
  volup: "Volume up", voldown: "Volume down", mail: "Mail", calc: "Calculator", mycomputer: "File manager",
  browser: "Web browser", www_back: "Browser back", www_forward: "Browser forward", www_stop: "Browser stop",
  www_refresh: "Browser refresh", www_favorites: "Bookmarks", media_player: "Media player",
  brightness_up: "Screen brighter", brightness_down: "Screen dimmer",
};
const CODE_MAP = {
  Escape: "esc", Backquote: "grave", Minus: "minus", Equal: "equal", Backspace: "backspace", Tab: "tab",
  BracketLeft: "lbracket", BracketRight: "rbracket", Backslash: "backslash", CapsLock: "capslock",
  Semicolon: "semicolon", Quote: "quote", Enter: "enter", Comma: "comma", Period: "period", Slash: "slash",
  Space: "space", PrintScreen: "printscreen", ScrollLock: "scrolllock", Pause: "pause", Insert: "insert",
  Home: "home", PageUp: "pgup", Delete: "delete", End: "end", PageDown: "pgdn", ArrowRight: "right",
  ArrowLeft: "left", ArrowDown: "down", ArrowUp: "up", NumLock: "numlock", ContextMenu: "app",
  NumpadDivide: "kp_slash", NumpadMultiply: "kp_asterisk", NumpadSubtract: "kp_minus", NumpadAdd: "kp_plus",
  NumpadEnter: "kp_enter", NumpadDecimal: "kp_period", IntlBackslash: "nonus_backslash",
  ControlLeft: "lctrl", ShiftLeft: "lshift", AltLeft: "lalt", MetaLeft: "lwin", OSLeft: "lwin",
  ControlRight: "rctrl", ShiftRight: "rshift", AltRight: "ralt", MetaRight: "rwin", OSRight: "rwin",
};
export const MODS = ["lctrl", "lshift", "lalt", "lwin", "rctrl", "rshift", "ralt", "rwin"];

export function codeToName(code) {
  if (CODE_MAP[code]) return CODE_MAP[code];
  let m;
  if ((m = code.match(/^Key([A-Z])$/))) return m[1].toLowerCase();
  if ((m = code.match(/^Digit(\d)$/))) return m[1];
  if ((m = code.match(/^F(\d+)$/))) return "f" + m[1];
  if ((m = code.match(/^Numpad(\d)$/))) return "kp_" + m[1];
  return null;
}

const SHORT = { ctrl: "Ctrl", shift: "Shift", alt: "Alt", win: "Super", super: "Super", meta: "Super" };
export function keyLabel(k) {
  if (!k) return "";
  if (KEY_LABEL[k]) return KEY_LABEL[k];
  if (SHORT[k]) return SHORT[k];
  if (/^f\d+$/.test(k)) return k.toUpperCase();
  if (k.startsWith("kp_")) return "Keypad " + k.slice(3);
  return k.length === 1 ? k.toUpperCase() : k;
}

export function describe(action, macros = []) {
  if (!action) return "";
  if (action === "disabled" || action === "none") return "Does nothing";
  if (action === "fn") return "Fn";
  if (action.startsWith("special(")) return "Built-in keyboard function";
  if (action.startsWith("media:")) return "Media " + action.slice(6);
  if (MEDIA_LABEL[action]) return MEDIA_LABEL[action];
  if (action.startsWith("macro:")) {
    const [, id, mode, n] = action.split(":");
    const mac = macros.find((x) => x.id === +id);
    const name = mac ? `“${mac.name}”` : `#${id}`;
    const how = mode === "hold" ? "while held" : mode === "toggle" ? "until another key" : `${n || 1}×`;
    return `Macro ${name}, ${how}`;
  }
  return action.split("+").map(keyLabel).join(" + ");
}

/** Split a macro spec into display steps. Mirrors compile_macro's tokenizer. */
export function macroSteps(spec) {
  const out = [];
  const re = /"([^"]*)"|(\S+)/g;
  let m;
  while ((m = re.exec(spec || ""))) {
    if (m[1] !== undefined) { out.push({ kind: "text", label: m[1] }); continue; }
    const t = m[2];
    if (/^\d+ms$/.test(t)) out.push({ kind: "wait", label: t });
    else if (t[0] === "+" && t.length > 1) out.push({ kind: "down", label: keyLabel(t.slice(1)) });
    else if (t[0] === "-" && t.length > 1) out.push({ kind: "up", label: keyLabel(t.slice(1)) });
    else out.push({ kind: "tap", label: t.split("+").map(keyLabel).join(" + ") });
  }
  return out;
}
