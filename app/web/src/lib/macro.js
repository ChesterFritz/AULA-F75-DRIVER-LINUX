// Macro steps <-> the backend's spec text <-> stored key events.
//
// A step is one of:
//   { kind: "text", text }        type some text
//   { kind: "keys", keys }        press a key or shortcut, e.g. "lctrl+c"
//   { kind: "wait", ms }          pause
//   { kind: "down", key }         hold a key down (advanced)
//   { kind: "up", key }           let a held key go (advanced)
import { keyLabel } from "./labels.js";

export const MACRO_BYTES = 512;   // the keyboard's macro memory, shared by all macros
const GAP = 30;                   // pauses at or below this are just typing speed, not real waits

let uid = 0;
export const step = (kind, extra = {}) => ({ id: ++uid, kind, ...extra });

// ---------- steps -> spec (what /api/macro compiles) ----------
export function stepsToSpec(steps) {
  const out = [];
  for (const s of steps) {
    if (s.kind === "text" && s.text) {
      // a double quote can't sit inside quotes, so type it as Shift + '
      s.text.split('"').forEach((part, i) => {
        if (i) out.push("lshift+quote");
        if (part) out.push(`"${part}"`);
      });
    } else if (s.kind === "keys" && s.keys) out.push(s.keys);
    else if (s.kind === "wait" && s.ms > 0) out.push(`${Math.round(s.ms)}ms`);
    else if (s.kind === "down" && s.key) out.push("+" + s.key);
    else if (s.kind === "up" && s.key) out.push("-" + s.key);
  }
  return out.join(" ");
}

// ---------- spec text -> steps (for the "edit as text" view) ----------
export function specToSteps(spec) {
  const out = [];
  const re = /"([^"]*)"|(\S+)/g;
  let m;
  while ((m = re.exec(spec || ""))) {
    if (m[1] !== undefined) { out.push(step("text", { text: m[1] })); continue; }
    const t = m[2];
    if (/^\d+ms$/.test(t)) out.push(step("wait", { ms: parseInt(t) }));
    else if (t[0] === "+" && t.length > 1) out.push(step("down", { key: t.slice(1) }));
    else if (t[0] === "-" && t.length > 1) out.push(step("up", { key: t.slice(1) }));
    else out.push(step("keys", { keys: t }));
  }
  return out;
}

// ---------- raw key events -> friendly steps ----------
// events: [{ name, down, delay }] where delay is the pause *after* that event.
const MODS = ["lctrl", "lshift", "lalt", "lwin", "rctrl", "rshift", "ralt", "rwin"];
const PLAIN = { space: " ", minus: "-", equal: "=", lbracket: "[", rbracket: "]", backslash: "\\",
  semicolon: ";", quote: "'", grave: "`", comma: ",", period: ".", slash: "/" };
const SHIFTED = { 1: "!", 2: "@", 3: "#", 4: "$", 5: "%", 6: "^", 7: "&", 8: "*", 9: "(", 0: ")",
  minus: "_", equal: "+", lbracket: "{", rbracket: "}", backslash: "|", semicolon: ":", quote: '"',
  grave: "~", comma: "<", period: ">", slash: "?" };

/** The character a key combo types, or null if it isn't plain typing. */
function charOf(names) {
  const [a, b] = names;
  if (names.length === 1) {
    if (/^[a-z0-9]$/.test(a)) return a;
    return PLAIN[a] ?? null;
  }
  if (names.length === 2 && (a === "lshift" || a === "rshift")) {
    if (/^[a-z]$/.test(b)) return b.toUpperCase();
    return SHIFTED[b] ?? null;
  }
  return null;
}

export function eventsToSteps(events, minWait = GAP) {
  const raw = [];
  const held = [];            // modifiers currently down: { name, used }
  const pending = new Set();  // normal keys pressed but not yet released
  const pause = (d) => { if (d > minWait && raw.length) raw.push(step("wait", { ms: d })); };
  for (const e of events) {
    if (MODS.includes(e.name)) {
      const k = held.findIndex((h) => h.name === e.name);
      if (e.down) { if (k < 0) held.push({ name: e.name, used: false }); continue; }
      if (k < 0) { raw.push(step("up", { key: e.name })); pause(e.delay); continue; }
      const [h] = held.splice(k, 1);
      if (!h.used) raw.push(step("keys", { keys: [...held.map((x) => x.name), h.name].join("+") }));  // modifier tapped alone
      pause(e.delay);
      continue;
    }
    if (e.down) {
      held.forEach((h) => (h.used = true));
      raw.push(step("keys", { keys: [...held.map((x) => x.name), e.name].join("+") }));
      pending.add(e.name);
      continue;   // how long a key is held isn't a pause
    }
    if (pending.has(e.name)) pending.delete(e.name);
    else raw.push(step("up", { key: e.name }));
    pause(e.delay);
  }
  while (raw.at(-1)?.kind === "wait") raw.pop();   // a pause at the very end does nothing
  // merge 2+ typed characters in a row into one "type text" step
  const out = [];
  for (let k = 0; k < raw.length; k++) {
    const ch = raw[k].kind === "keys" ? charOf(raw[k].keys.split("+")) : null;
    let run = ch === null ? "" : ch, e = k;
    while (ch !== null && e + 1 < raw.length && raw[e + 1].kind === "keys") {
      const c = charOf(raw[e + 1].keys.split("+"));
      if (c === null) break;
      run += c; e++;
    }
    if (ch !== null && e > k) { out.push(step("text", { text: run })); k = e; }
    else out.push(raw[k]);
  }
  return out;
}

/** "+lctrl +c 12ms -c -lctrl" (what the server reports) -> events */
export function parseEvents(str) {
  const events = [];
  for (const t of (str || "").split(/\s+/)) {
    if (/^\d+ms$/.test(t) && events.length) events[events.length - 1].delay = parseInt(t);
    else if (/^[+-]/.test(t)) events.push({ name: t.slice(1), down: t[0] === "+", delay: 0 });
  }
  return events;
}

// ---------- display helpers ----------
// left-hand modifiers are what people mean by "Ctrl", so drop the "Left"
const SIMPLE = { lctrl: "Ctrl", lshift: "Shift", lalt: "Alt", lwin: "Super" };
export const comboLabel = (keys) => (keys || "").split("+").filter(Boolean).map((k) => SIMPLE[k] ?? keyLabel(k)).join(" + ");

export function stepLabel(s) {
  if (s.kind === "text") return `“${s.text}”`;
  if (s.kind === "keys") return comboLabel(s.keys);
  if (s.kind === "wait") return s.ms >= 1000 ? `${+(s.ms / 1000).toFixed(2)} s` : `${s.ms} ms`;
  if (s.kind === "down") return `Hold ${comboLabel(s.key)}`;
  return `Release ${comboLabel(s.key)}`;
}

/** Approximate key events a list of steps compiles to (4 bytes each on the keyboard). */
export function eventCount(steps) {
  let n = 0;
  for (const s of steps) {
    if (s.kind === "text") for (const ch of s.text) n += /[A-Z]/.test(ch) || '!@#$%^&*()_+{}|:"~<>?'.includes(ch) ? 4 : 2;
    else if (s.kind === "keys") n += 2 * s.keys.split("+").filter(Boolean).length;
    else if (s.kind === "down" || s.kind === "up") n += 1;
  }
  return n;
}
export const macroBytes = (name, events) => 4 + 1 + 2 * Math.min(30, (name || "").length) + 4 * events;

export const TEMPLATES = [
  { name: "Copy & paste", hint: "Copy, wait a moment, paste",
    steps: () => [step("keys", { keys: "lctrl+c" }), step("wait", { ms: 100 }), step("keys", { keys: "lctrl+v" })] },
  { name: "Type a message", hint: "Types a sentence for you",
    steps: () => [step("text", { text: "Thanks! I'll get back to you soon." })] },
  { name: "Select all & copy", hint: "Grab everything in a box",
    steps: () => [step("keys", { keys: "lctrl+a" }), step("keys", { keys: "lctrl+c" })] },
  { name: "Open a terminal", hint: "Ctrl + Alt + T",
    steps: () => [step("keys", { keys: "lctrl+lalt+t" })] },
];
