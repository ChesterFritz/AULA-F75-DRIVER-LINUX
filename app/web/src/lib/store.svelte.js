import { api, write } from "./api.js";
import { buildLayout } from "./layout.js";

export const app = $state({
  catalog: null,
  layout: null,
  state: null,       // full keyboard state from /api/state
  error: "",         // why the keyboard isn't available
  loading: true,
  save: "",          // "", "saving", "saved"
  tab: "lighting",
  layer: "base",
  selectedKey: null,
  assignMacro: null, // macro id waiting to be put on a key (set from the Macros tab)
  debug: false,
  preview: null,     // debug: preview another effect without writing it
  guide: { keys: [], key: null, os: "win" }, // Manual tab: keys lit on the preview, key filter, F-row mode
});

export const toasts = $state([]);
let toastId = 0;
export function toast(msg, kind = "ok") {
  const t = { id: ++toastId, msg, kind };
  toasts.push(t);
  setTimeout(() => {
    const i = toasts.findIndex((x) => x.id === t.id);
    if (i >= 0) toasts.splice(i, 1);
  }, kind === "err" ? 5500 : 2600);
}

let retry;
export async function load() {
  app.loading = true;
  let s;
  try { s = await api("state"); } catch (e) { s = { connected: false, error: e.message }; }
  app.loading = false;
  clearTimeout(retry);
  if (!s.connected) {
    app.state = null;
    app.error = s.error;
    retry = setTimeout(load, 6000);
    return;
  }
  app.error = "";
  app.state = s;
}

let savedTimer;
/** Write to the keyboard; shows progress in the status pill, errors as toasts. */
export async function act(path, body, msg) {
  app.save = "saving";
  try {
    const r = await write(path, body);
    app.save = "saved";
    clearTimeout(savedTimer);
    savedTimer = setTimeout(() => (app.save = ""), 1800);
    if (msg) toast(msg);
    return r;
  } catch (e) {
    app.save = "";
    toast(e.message, "err");
    throw e;
  }
}

let lightTimer;
export function setLighting(change) {
  const s = app.state;
  const { mode } = change;
  s.lighting.mode = mode;
  const ms = s.lighting.modes[mode];
  if (ms) for (const k of ["brightness", "speed", "color"]) if (k in change) ms[k] = change[k];
  clearTimeout(lightTimer);
  lightTimer = setTimeout(() => {
    const body = { mode };
    if (ms) Object.assign(body, { brightness: ms.brightness, speed: ms.speed, color: ms.color });
    act("lighting", body).catch(load);
  }, 200);
}

export async function setPalette(mode, slot, rgb) {
  const ms = app.state.lighting.modes[mode];
  ms.palette[slot] = rgb;
  ms.color = slot;
  try {
    await act("palette", { mode, slot, rgb });
    await act("lighting", { mode, color: slot });
  } catch { load(); }
}

export async function init() {
  const q = new URLSearchParams(location.search);
  app.debug = !!q.get("debug");
  app.preview = q.get("preview");
  if (["keys", "macros", "backups", "power", "manual"].includes(q.get("tab"))) app.tab = q.get("tab");
  if (q.get("key")) app.selectedKey = q.get("key");
  try {
    app.catalog = await api("catalog");
    app.layout = buildLayout();
  } catch (e) {
    app.error = e.message;
    app.loading = false;
    return;
  }
  await load();
  setInterval(() => api("ping").catch(() => {}), 5000);
  setInterval(refreshBattery, 5000);
  document.addEventListener("visibilitychange", refreshBattery);
  window.addEventListener("focus", refreshBattery);
  checkBattery();
}

// Battery: refreshed every 5 s while the window is visible; one warning when it gets low while unplugged.
let warnedLow = false;
function checkBattery() {
  const b = app.state?.battery;
  if (!b) return;
  if (b.charging || b.percent > 20) warnedLow = false;
  else if (b.percent <= 15 && !warnedLow) {
    warnedLow = true;
    toast(`Keyboard battery is at ${b.percent}%. Plug in the cable to charge it.`, "err");
  }
}
let batteryBusy = false;
export async function refreshBattery() {
  if (!app.state || app.save === "saving" || document.hidden || batteryBusy) return;
  batteryBusy = true;
  try {
    const r = await api("battery");
    // null = keyboard asleep / no answer: keep showing the last reading
    if (app.state && r.battery) { app.state.battery = r.battery; checkBattery(); }
  } catch { /* next tick */ } finally { batteryBusy = false; }
}
