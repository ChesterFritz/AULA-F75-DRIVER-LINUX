// The EPOMAKER x AULA F75 quick start guide (English section of the printed manual), as data.
// Key names match layout.js, so the Manual tab can light them up on the keyboard.

export const KEY_NAME = {
  fn: "Fn", esc: "Esc", lwin: "Win", lshift: "L Shift", grave: "` ~", tab: "Tab", backslash: "\\ |",
  up: "↑", down: "↓", left: "←", right: "→", delete: "Del", end: "End", wheel: "Knob",
};
export const keyName = (k) => KEY_NAME[k] ?? (/^f\d+$/.test(k) ? k.toUpperCase() : k.toUpperCase());

const sc = (keys, what, extra = {}) => ({ keys, what, ...extra });

export const GROUPS = [
  {
    id: "system", title: "Modes & system", color: "#3b6dff", text: "#fff",
    items: [
      sc(["fn", "w"], "Windows mode", { tip: "The one to use on Linux: F1–F12 are plain F-keys, Fn adds media keys." }),
      sc(["fn", "e"], "Mac mode"),
      sc(["fn", "q"], "Android mode"),
      sc(["fn", "b"], "Check battery", { tip: "Number keys 1–0 light green for the charge left; red when low. Works in 2.4G and Bluetooth.", goto: "power" }),
      sc(["fn", "esc"], "Reset the keyboard to factory settings", { hold: "Hold 3 s", warn: true,
        tip: "Also wipes your key remaps and macros. Save a backup first.", goto: "backups" }),
    ],
  },
  {
    id: "connect", title: "Connections", color: "#19d3c5",
    items: [
      sc(["fn", "1"], "Bluetooth device 1", { hold: "Hold to pair", tip: "Long press: pair a new device. Short press: switch to it." }),
      sc(["fn", "2"], "Bluetooth device 2", { hold: "Hold to pair", tip: "Long press: pair a new device. Short press: switch to it." }),
      sc(["fn", "3"], "Bluetooth device 3", { hold: "Hold to pair", tip: "Long press: pair a new device. Short press: switch to it." }),
      sc(["fn", "grave"], "Connect over 2.4G", { hold: "Hold to pair", tip: "Long press to pair with the USB receiver." }),
      sc(["fn", "lshift"], "Charging indicator light effect"),
    ],
  },
  {
    id: "light", title: "Lighting", color: "#ff3ea5",
    items: [
      sc(["fn", "backslash"], "Next backlight effect, or backlight off", { goto: "lighting" }),
      sc(["fn", "tab"], "Change the backlight colour", { goto: "lighting" }),
      sc(["fn", "up"], "Backlight brighter"),
      sc(["fn", "down"], "Backlight dimmer"),
      sc(["fn", "right"], "Effect faster"),
      sc(["fn", "left"], "Effect slower"),
    ],
  },
  {
    id: "win", title: "Windows mode only", color: "#ff7a1a",
    items: [
      sc(["fn", "lwin"], "Win key lock", { tip: "Stops the Win/Super key opening the launcher, handy for games." }),
      sc(["fn", "u"], "Print Screen"),
      sc(["fn", "i"], "Scroll Lock"),
      sc(["fn", "o"], "Pause"),
      sc(["fn", "delete"], "Insert"),
      sc(["fn", "end"], "Home"),
    ],
  },
];

// Press the knob for 3–5 s to switch between the two knob modes.
export const KNOB = [
  { id: "gaming", title: "Gaming mode", light: "knob light breathes",
    actions: [["Press", "Next backlight effect"], ["Turn right", "Backlight brighter"], ["Turn left", "Backlight dimmer"]] },
  { id: "office", title: "Office mode", light: "knob light stays on",
    actions: [["Press", "Mute"], ["Turn right", "Volume up"], ["Turn left", "Volume down"]] },
];

// What F1–F12 do on their own and together with Fn, per system mode.
const MEDIA = ["Screen dimmer", "Screen brighter", "Switch windows", "Show desktop", "Backlight dimmer", "Backlight brighter",
  "Previous track", "Play / pause", "Next track", "Mute", "Volume down", "Volume up"];
const PLAIN = MEDIA.map((_, i) => `Normal F${i + 1} key`);
const WIN_FN = ["Browser home", "Mail", "Switch windows", "File explorer", "Backlight dimmer", "Backlight brighter",
  "Previous track", "Play / pause", "Next track", "Mute", "Volume down", "Volume up"];
export const OS_MODES = [
  { id: "win", label: "Windows", combo: ["fn", "w"], plain: PLAIN, fn: WIN_FN },
  { id: "mac", label: "Mac", combo: ["fn", "e"], plain: MEDIA, fn: PLAIN },
  { id: "android", label: "Android", combo: ["fn", "q"], plain: MEDIA, fn: PLAIN },
];

export const HOWTO = [
  {
    id: "bt", title: "Pair over Bluetooth", keys: ["fn", "1"],
    steps: [
      "Slide the switch on the back to BT.",
      "Hold Fn + 1, 2 or 3 for 3–5 seconds until that key blinks fast in blue. The keyboard is ready to pair.",
      "On your computer, open Bluetooth, find “AULA-F75 3.0/5.0” and connect. The key stops blinking once it's connected.",
      "Later, tap Fn + 1 / 2 / 3 to switch between the three paired devices.",
    ],
    note: "Bluetooth polls at 125 Hz. Use the receiver or the cable for gaming (1000 Hz).",
  },
  {
    id: "24g", title: "Pair the 2.4G receiver", keys: ["fn", "grave"],
    steps: [
      "Slide the switch to 2.4G. The ` ~ key blinks.",
      "Hold Fn + ` ~ for 3–5 seconds until the key blinks fast in green.",
      "Plug the 2.4G receiver into the computer. When the light stops blinking, it's connected.",
    ],
    note: "This app talks to the keyboard through the receiver, so settings can be changed wirelessly.",
  },
  {
    id: "wired", title: "Use it wired", keys: ["4"],
    steps: [
      "Slide the switch to the middle position.",
      "Plug in the USB-C cable. The 4 $ key lights white for 2 seconds and it's connected.",
    ],
  },
  {
    id: "battery", title: "Check the battery", keys: ["fn", "b"], goto: "power",
    steps: [
      "In 2.4G or Bluetooth mode, press and hold Fn + B.",
      "The number keys 1 to 0 light up green: all ten means full, fewer means less charge left. Red lights mean the battery is low.",
    ],
    note: "The Power tab shows the exact percentage.",
  },
  {
    id: "fnkey", title: "See the current mode", keys: ["fn"],
    steps: [
      "Hold Fn. The keys for the current connection (Bluetooth 1 / 2 / 3 or 2.4G) and system mode (Android / Win / Mac) light up.",
    ],
  },
  {
    id: "reset", title: "Factory reset", keys: ["fn", "esc"], goto: "backups", warn: true,
    steps: [
      "Hold Fn + Esc for 3 seconds.",
      "Lighting, key remaps and macros go back to factory settings.",
    ],
    note: "Save a backup in the Backups tab first, so you can restore your setup afterwards.",
  },
  {
    id: "switches", title: "Swap keycaps and switches", keys: [],
    steps: [
      "Pull the keycap off with the keycap puller.",
      "Line the switch puller up vertically on the switch, so its teeth grip the clips at the top and bottom of the switch.",
      "Squeeze until the switch lets go of the plate, then pull it straight up.",
      "Before fitting a switch, check that its metal pins are clean and straight.",
      "Line it up with the logo facing north (towards the back) so the pins meet the holes in the PCB.",
      "Push it straight down until it clicks into the plate, then test the key.",
    ],
    note: "If a key doesn't work after a swap, a pin is probably bent: pull the switch, straighten the pin and try again. Never force a switch in.",
    link: ["Epomaker's step-by-step guide", "https://epomaker.com/blogs/guides/diy-guide-how-to-remove-and-replace-your-mechanical-keyboard-switches"],
  },
];

export const SPECS = [
  ["Model", "EPOMAKER x AULA F75"],
  ["Keys", "80 + knob (ANSI), 81 + knob (ISO)"],
  ["Mounting", "Gasket"],
  ["Stabilisers", "Plate-mounted"],
  ["Case", "ABS plastic"],
  ["Plate", "PC"],
  ["PCB", "3/5-pin hot-swap"],
  ["Connections", "USB-C cable, Bluetooth 5.0, 2.4G"],
  ["Anti-ghosting", "NKRO in all modes"],
  ["Polling rate", "1000 Hz (USB, 2.4G), 125 Hz (Bluetooth)"],
  ["Battery", "4000 mAh"],
  ["Size", "323 × 143 × 43 mm"],
  ["Weight", "1.02 kg"],
];

export const SUPPORT = {
  email: "support@epomaker.com",
  site: "https://epomaker.com",
  text: "Email with your order number and a description of the problem. Epomaker usually replies within 24 hours.",
  warranty: "1-year warranty on factory defects when bought from epomaker.com or an official Epomaker store. Bought elsewhere? Contact the seller.",
};

/** Every shortcut that uses `key`, for the keyboard tooltip and the key filter. */
export function shortcutsFor(key, os = "win") {
  const out = [];
  for (const g of GROUPS) for (const it of g.items) if (it.keys.includes(key) && key !== "fn") out.push(it);
  const m = OS_MODES.find((x) => x.id === os);
  const f = /^f(\d+)$/.exec(key);
  if (f) out.push(sc([key], m.plain[f[1] - 1]), sc(["fn", key], m.fn[f[1] - 1]));
  return out;
}
