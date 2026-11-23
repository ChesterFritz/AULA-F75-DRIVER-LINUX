// Keychron mouse state, kept apart from the AULA keyboard store.
import { api } from "./api.js";
import { act } from "./store.svelte.js";
import { keyLabel } from "./labels.js";

export const mouse = $state({
  data: null,       // { name, pid, buttons: [{id, index, label, action}], battery, art }
  catalog: null,
  error: "",
  loading: false,
  selected: new URLSearchParams(location.search).get("button"), // button id (debug: ?button=)
  view: 0,          // which Keychron photo is shown (0 = top, 1 = side)
  section: "buttons", // panel under the mouse: "buttons" | "dpi" | "poll" (the launcher's sidebar)
});

/** Save DPI steps and the active step to the mouse. */
export async function setMouseDpi(steps, current) {
  const r = await act("mouse-settings", { dpi: { steps, current } }, `DPI set to ${steps[current]}`);
  if (r.info && mouse.data) mouse.data.info = r.info;
  return r;
}

/** Switch the mouse to another polling rate (index into its list). */
export async function setMousePolling(index) {
  const hz = mouse.data?.info?.polling.steps[index];
  const r = await act("mouse-settings", { polling: index }, `Polling rate set to ${hz ?? "?"} Hz`);
  if (r.info && mouse.data) mouse.data.info = r.info;
  return r;
}

/** Click to select, click the same button again to deselect. Shows the photo the button is on. */
export function selectMouseButton(id) {
  mouse.selected = !id || mouse.selected === id ? null : id;
  if (mouse.selected) mouse.section = "buttons";
  const spot = mouse.selected && mouse.data?.art?.spots[mouse.selected];
  if (spot) mouse.view = spot.image;
}

export async function resetAllMouse() {
  const changed = (mouse.data?.buttons ?? []).filter((b) => b.action !== "default");
  if (!changed.length || !confirm("Put every mouse button back to its normal job?")) return;
  try { for (const b of changed) await remapMouse(b.id, "default"); } catch { await loadMouse(); }
}

let retry;
let inFlight = false;
/** quiet = background retry: keep showing the "not found / asleep" message instead of a spinner. */
export async function loadMouse(quiet = false) {
  if (inFlight) return;
  inFlight = true;
  if (!quiet) mouse.loading = true;
  let r;
  try { r = await api("mouse"); } catch (e) { r = { connected: false, error: e.message }; }
  inFlight = false;
  mouse.loading = false;
  clearTimeout(retry);
  if (r.catalog) mouse.catalog = r.catalog;
  if (!r.connected) {
    mouse.data = null;
    mouse.error = r.error;
    retry = setTimeout(() => { if (!mouse.data) loadMouse(true); }, 6000);
    return;
  }
  mouse.error = "";
  mouse.data = { name: r.name, pid: r.pid, buttons: r.buttons, info: r.info, art: r.art };
  const sec = new URLSearchParams(location.search).get("section"); // debug: ?section=dpi
  if (sec && ["buttons", "dpi", "poll"].includes(sec)) mouse.section = sec;
  if (!mouse.selected || !r.buttons.some((b) => b.id === mouse.selected)) mouse.selected = null;
  else if (r.art?.spots[mouse.selected]) mouse.view = r.art.spots[mouse.selected].image;
}

// Battery, DPI and polling rate: refreshed while the Mouse tab is open
// (the DPI button on the mouse can change them at any time).
export async function refreshMouseInfo() {
  if (!mouse.data || document.hidden) return;
  try { const r = await api("mouse-info"); if (r.info && mouse.data) mouse.data.info = r.info; } catch {}
}

export function mouseImage(n) {
  const t = new URLSearchParams(location.search).get("t") || "";
  return `api/mouse-image/${mouse.data.pid.toString(16).padStart(4, "0")}/${n}?t=${encodeURIComponent(t)}`;
}

export async function remapMouse(button, action) {
  const b = mouse.data?.buttons.find((x) => x.id === button);
  const r = await act("mouse-remap", { button, action }, `${b?.label ?? button} → ${describeMouse(action)}`);
  if (b) b.action = r.action;
  return r;
}

export const MOUSE_LABEL = {
  left: "Left click", right: "Right click", middle: "Middle click", back: "Back", forward: "Forward",
  "double-left": "Double click", "scroll-up": "Scroll up", "scroll-down": "Scroll down",
  "scroll-left": "Scroll left", "scroll-right": "Scroll right",
};
export const MEDIA_LABEL = {
  play: "Play / pause", stop: "Stop", next: "Next track", prev: "Previous track",
  volup: "Volume up", voldown: "Volume down", mute: "Mute", media_player: "Media player",
};
export const CYCLE_LABEL = { loop: "Cycle", next: "Next", prev: "Previous" };
export const SHORTCUT_LABEL = {
  copy: "Copy", cut: "Cut", paste: "Paste", refresh: "Refresh", screenshot: "Screenshot",
  "switch-app": "Switch app", "task-view": "Task view", "zoom-in": "Zoom in", "zoom-out": "Zoom out",
  "brightness-up": "Screen brighter", "brightness-down": "Screen dimmer", calculator: "Calculator",
  "my-computer": "File manager", "home-page": "Browser home", email: "Email",
};

/** Text action from keychron_mouse.py -> words for people. */
export function describeMouse(a) {
  if (!a) return "";
  if (a === "default") return "Its normal job";
  if (a === "disable") return "Does nothing";
  const [kind, name] = a.split(":");
  if (kind === "mouse") return MOUSE_LABEL[name] ?? name;
  if (kind === "media") return MEDIA_LABEL[name] ?? name;
  if (kind === "dpi") return `DPI: ${CYCLE_LABEL[name]?.toLowerCase() ?? name}`;
  if (kind === "poll") return `Polling rate: ${CYCLE_LABEL[name]?.toLowerCase() ?? name}`;
  if (kind === "shortcut") return SHORTCUT_LABEL[name] ?? name;
  if (kind === "raw") return "Set in another app";
  return a.split("+").map(keyLabel).join(" + ");
}
