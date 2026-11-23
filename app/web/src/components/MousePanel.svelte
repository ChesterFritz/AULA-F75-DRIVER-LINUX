<script>
  // Keychron mouse buttons, laid out like Keychron Launcher: a full-width picker under the mouse.
  // Select a button on the mouse (click again to deselect), then click what it should do;
  // the choice is saved to the mouse straight away.
  import { MousePointerClick, Keyboard, Music, Gauge, Activity, Command, Ban, RotateCcw, X, ArrowRight, Plus, Minus, Check } from "@lucide/svelte";
  import { mouse, loadMouse, remapMouse, selectMouseButton, setMouseDpi, setMousePolling, describeMouse, MOUSE_LABEL, MEDIA_LABEL, CYCLE_LABEL, SHORTCUT_LABEL } from "../lib/mouse.svelte.js";
  import { keyLabel, codeToName, MODS } from "../lib/labels.js";
  import Segmented from "./Segmented.svelte";

  const TABS = [
    { value: "mouse", label: "Basic buttons", icon: MousePointerClick },
    { value: "keys", label: "Key combinations", icon: Keyboard },
    { value: "media", label: "Multimedia", icon: Music },
    { value: "shortcut", label: "Shortcuts", icon: Command },
    { value: "dpi", label: "DPI switch", icon: Gauge },
    { value: "poll", label: "Rate switch", icon: Activity },
    { value: "off", label: "Disable", icon: Ban },
  ];
  const range = (n, f) => Array.from({ length: n }, (_, i) => f(i));
  const KEY_GROUPS = [
    ["Letters", range(26, (i) => String.fromCharCode(97 + i))],
    ["Numbers", range(10, (i) => String((i + 1) % 10))],
    ["Function keys", range(12, (i) => `f${i + 1}`)],
    ["Editing", ["esc", "tab", "enter", "space", "backspace", "delete", "insert", "capslock"]],
    ["Navigation", ["up", "down", "left", "right", "home", "end", "pgup", "pgdn"]],
    ["Symbols", ["grave", "minus", "equal", "lbracket", "rbracket", "backslash", "semicolon", "quote", "comma", "period", "slash"]],
    ["System", ["printscreen", "scrolllock", "pause", "app"]],
  ];
  const ARROWS = { up: "↑", down: "↓", left: "←", right: "→" };
  const COMBO_MODS = [["lctrl", "Ctrl"], ["lshift", "Shift"], ["lalt", "Alt"], ["lwin", "Super"]];

  const btn = $derived(mouse.data?.buttons.find((b) => b.id === mouse.selected) ?? null);
  const current = $derived(btn?.action ?? "");
  const changedList = $derived((mouse.data?.buttons ?? []).filter((b) => b.action !== "default"));
  const cat = $derived(mouse.catalog ?? { mouse: [], media: [], cycle: [], shortcut: [] });

  let tab = $state("mouse");
  let mods = $state([]);
  let captured = $state("");
  let listening = $state(false);
  let busy = $state(false);
  let openedFor = "";

  // Open the tab that matches what the picked button does now.
  $effect(() => {
    if (!btn || openedFor === btn.id) return;
    openedFor = btn.id;
    const [kind] = btn.action.split(":");
    tab = btn.action === "disable" ? "off" : kind === "mouse" || btn.action === "default" ? "mouse"
      : kind === "media" ? "media" : kind === "shortcut" ? "shortcut" : kind === "dpi" ? "dpi" : kind === "poll" ? "poll" : "keys";
    mods = tab === "keys" ? btn.action.split("+").filter((p) => MODS.includes(p)) : [];
  });

  async function assign(action) {
    if (!btn || busy) return;
    busy = true;
    try { await remapMouse(btn.id, action); } catch { await loadMouse(); } finally { busy = false; }
  }
  function toggleMod(m) {
    const next = mods.includes(m) ? mods.filter((x) => x !== m) : [...mods, m];
    mods = MODS.filter((x) => next.includes(x));
  }
  const withMods = (k) => [...mods, k].join("+");

  const held = new Set();
  function keydown(e) {
    if (e.key === "Tab" && !held.size) return;
    e.preventDefault();
    const n = codeToName(e.code);
    if (!n || e.repeat) return;
    if (!held.size) captured = "";
    held.add(n);
    captured = [...MODS.filter((x) => held.has(x)), ...[...held].filter((x) => !MODS.includes(x)).slice(0, 2)].join("+");
  }
  function keyup(e) { const n = codeToName(e.code); if (n) held.delete(n); }

  const locked = $derived(!btn || busy);
  const info = $derived(mouse.data?.info ?? null);


  // ---- sections (the launcher's sidebar: Customize / DPI Settings / Polling Rate)
  const SECTIONS = [
    { value: "buttons", label: "Buttons", icon: MousePointerClick },
    { value: "dpi", label: "DPI", icon: Gauge },
    { value: "poll", label: "Polling rate", icon: Activity },
  ];
  const limit = $derived(mouse.data?.art?.dpi_limit ?? [50, 26000]);
  const clampDpi = (v) => Math.min(limit[1], Math.max(limit[0], Math.round((+v || 0) / 50) * 50));

  // DPI: everything applies straight away, like Keychron Launcher.
  let steps = $state([]);
  let active = $state(0);
  let savingDpi = $state(false);
  $effect(() => {
    const d = info?.dpi;
    if (d && !savingDpi) { steps = [...d.steps]; active = d.current; }
  });
  async function applyDpi(nextSteps, nextActive) {
    nextSteps = nextSteps.map(clampDpi);
    nextActive = Math.min(nextActive, nextSteps.length - 1);
    steps = nextSteps; active = nextActive;            // show it at once
    savingDpi = true;
    try { await setMouseDpi(nextSteps, nextActive); }
    catch { if (info) { steps = [...info.dpi.steps]; active = info.dpi.current; } }
    finally { savingDpi = false; }
  }
  const editStep = (i, v) => applyDpi(steps.map((x, j) => (j === i ? v : x)), active);
  const addStep = () => steps.length < 5 && applyDpi([...steps, clampDpi(Math.min(limit[1], steps.at(-1) * 2))], active);
  const removeStep = (i) => steps.length > 1 && applyDpi(steps.filter((_, j) => j !== i), active > i ? active - 1 : active === i ? 0 : active);
  const DPI_PRESETS = [400, 800, 1200, 1600, 2400, 3200, 6400, 12000];

  // Polling rate: one click switches it.
  let savingPoll = $state(false);
  async function pickPoll(i) {
    if (savingPoll || i === info?.polling.current) return;
    savingPoll = true;
    try { await setMousePolling(i); } catch {} finally { savingPoll = false; }
  }
</script>

{#snippet chip(action, label, wide = false)}
  {@const on = current === action}
  {@const blocked = btn?.id === "left" && action === "disable"}
  <button type="button" disabled={locked || blocked} title={blocked ? "The left button can't be turned off" : on ? "Already set" : label}
          class="chip {wide ? 'col-span-2' : ''} {on ? 'chip-on' : ''}" onclick={() => !on && assign(action)}>{label}</button>
{/snippet}


<section class="area-list card mouse-panel grid w-full content-start gap-4 !p-4" style:background="linear-gradient(170deg, var(--color-surface) 60%, var(--tab-tint))">
  <div class="flex flex-wrap items-center gap-3 border-b-2 border-dashed border-ink/15 pb-3">
    <Segmented options={SECTIONS} bind:value={mouse.section} label="Mouse settings" />
    {#if info && mouse.section !== "buttons"}
      <span class="hint">Changes save to the mouse straight away.</span>
    {/if}
  </div>

  {#if mouse.section === "dpi"}
    {#if info}
      <div class="grid gap-4">
        <p class="hint m-0">Click a step to use it now. Change the numbers to set your own. The DPI button on the mouse cycles through these steps.</p>
        <div class="flex flex-wrap items-stretch gap-3">
          {#each steps as v, i (i)}
            {@const on = i === active}
            <div class="dpi-card {on ? 'dpi-on' : ''}">
              <button type="button" class="absolute inset-0 rounded-[inherit]" aria-pressed={on} disabled={savingDpi}
                      title={on ? "In use now" : `Use ${v} DPI now`} onclick={() => !on && applyDpi(steps, i)}></button>
              <span class="relative flex items-center justify-between gap-2 text-[.66rem] font-extrabold uppercase tracking-wider opacity-60 pointer-events-none">
                Step {i + 1}{#if on}<span class="inline-flex items-center gap-0.5"><Check size={12} strokeWidth={3.5} /> in use</span>{/if}
              </span>
              <label class="relative flex items-baseline gap-1">
                <input type="number" class="dpi-input" min={limit[0]} max={limit[1]} step="50" value={v} disabled={savingDpi}
                       aria-label="Step {i + 1} DPI" onchange={(e) => editStep(i, e.currentTarget.value)}
                       onkeydown={(e) => e.key === "Enter" && e.currentTarget.blur()} />
                <span class="text-xs font-extrabold opacity-60">DPI</span>
              </label>
              {#if steps.length > 1}
                <button type="button" class="relative self-start text-[.7rem] font-bold underline-offset-2 opacity-55 hover:underline hover:opacity-100"
                        disabled={savingDpi} onclick={() => removeStep(i)}><Minus size={11} strokeWidth={3} class="inline" /> remove</button>
              {/if}
            </div>
          {/each}
          {#if steps.length < 5}
            <button type="button" class="dpi-add" disabled={savingDpi} onclick={addStep}><Plus size={18} strokeWidth={3} /> Add step</button>
          {/if}
        </div>
        <div class="grid gap-2">
          <h4>Step {active + 1} · slide to fine-tune ({limit[0]}–{limit[1]})</h4>
          <input type="range" class="w-full max-w-2xl accent-[var(--tab)]" min={limit[0]} max={limit[1]} step="50" value={steps[active]}
                 disabled={savingDpi} oninput={(e) => (steps[active] = +e.currentTarget.value)}
                 onchange={(e) => editStep(active, e.currentTarget.value)} aria-label="DPI of step {active + 1}" />
          <div class="flex flex-wrap gap-1.5">
            {#each DPI_PRESETS.filter((x) => x >= limit[0] && x <= limit[1]) as x}
              <button type="button" class="chip !min-h-8 px-3 {steps[active] === x ? 'chip-on' : ''}" disabled={savingDpi}
                      onclick={() => editStep(active, x)}>{x}</button>
            {/each}
          </div>
        </div>
      </div>
    {:else}
      <p class="hint">Couldn't read the DPI settings from the mouse. Move it to wake it up.</p>
    {/if}
  {:else if mouse.section === "poll"}
    {#if info}
      <div class="grid gap-3">
        <p class="hint m-0">How often the mouse reports its position to the computer. Higher feels smoother but uses more battery.</p>
        <div class="flex flex-wrap gap-3">
          {#each info.polling.steps as hz, i}
            {@const on = i === info.polling.current}
            <button type="button" class="poll-card {on ? 'dpi-on' : ''}" aria-pressed={on} disabled={savingPoll} onclick={() => pickPoll(i)}>
              <span class="text-2xl font-black tabular-nums">{hz ?? "?"}<span class="ml-1 text-sm">Hz</span></span>
              <span class="text-xs font-bold opacity-60">{hz ? `every ${+(1000 / hz).toFixed(1)} ms` : ""}{on ? " · in use" : ""}</span>
            </button>
          {/each}
        </div>
        <p class="hint m-0">Connected by {info.mode}.</p>
      </div>
    {:else}
      <p class="hint">Couldn't read the polling rate from the mouse. Move it to wake it up.</p>
    {/if}
  {:else}
  <!-- what is selected -->
  <div class="flex min-h-12 flex-wrap items-center gap-3">
    {#if btn}
      <span class="-rotate-2 whitespace-nowrap rounded-xl border-[3px] border-ink bg-sun px-3 py-1.5 text-base font-black text-coal shadow-pop-sm">{btn.label}</span>
      <ArrowRight size={18} strokeWidth={3} class="text-ink/40" />
      <span class="text-base font-extrabold">{describeMouse(btn.action)}</span>
      {#if btn.action !== "default"}<span class="hint">· factory: its normal job</span>{/if}
      <span class="ml-auto flex gap-2">
        <button class="btn btn-line !min-h-0 !px-3 !py-1.5 text-xs" disabled={busy || btn.action === "default"} onclick={() => assign("default")}>
          <RotateCcw size={14} strokeWidth={3} /> Back to factory
        </button>
        <button class="btn btn-line !min-h-0 !px-3 !py-1.5 text-xs" title="Deselect (Esc)" onclick={() => selectMouseButton(null)}>
          <X size={14} strokeWidth={3} /> Deselect
        </button>
      </span>
    {:else}
      <span class="grid size-10 rotate-6 place-items-center rounded-xl border-[3px] border-ink bg-sun text-coal shadow-pop-sm"><MousePointerClick size={20} strokeWidth={2.6} /></span>
      <div>
        <p class="m-0 font-black">Select a button on the mouse above</p>
        <p class="hint m-0">Click a label or dot to select it, click it again to deselect. Then pick what it should do here.</p>
      </div>
    {/if}
  </div>

  <Segmented options={TABS} bind:value={tab} label="What the button does" />

  <div class="grid gap-4 {btn ? '' : 'dim'}">
    {#if tab === "mouse"}
      <div class="chips">{#each cat.mouse as m}{@render chip(`mouse:${m}`, MOUSE_LABEL[m] ?? m, true)}{/each}</div>
    {:else if tab === "keys"}
      <div class="flex flex-wrap items-center gap-2">
        <span class="text-xs font-extrabold uppercase tracking-wider text-ink/50">Hold</span>
        {#each COMBO_MODS as [m, label] (m)}
          <button type="button" class="chip !min-h-9 px-4 {mods.includes(m) ? 'chip-on' : ''}" aria-pressed={mods.includes(m)}
                  title={mods.includes(m) ? "Click again to remove" : `Add ${label}`} onclick={() => toggleMod(m)}>{label}</button>
        {/each}
        <span class="hint">{mods.length ? "+ click a key below" : "(optional) then click a key"}</span>
        <span class="ml-auto flex items-center gap-2">
          <input class="input !w-56 cursor-pointer !py-1.5 font-black caret-transparent {listening ? 'animate-pulse bg-sun/30' : ''}" readonly
                 value={captured ? captured.split("+").map(keyLabel).join(" + ") : ""}
                 placeholder={listening ? "Press keys now…" : "…or click here and press keys"}
                 onkeydown={keydown} onkeyup={keyup}
                 onfocus={() => { held.clear(); listening = true; }} onblur={() => { held.clear(); listening = false; }}>
          <button class="btn btn-primary !min-h-0 !py-1.5" disabled={!captured || locked} onclick={() => assign(captured)}>Use</button>
        </span>
      </div>
      {#each KEY_GROUPS as [title, keys] (title)}
        <div class="group"><h4>{title}</h4>
          <div class="chips">{#each keys as k}{@render chip(withMods(k), ARROWS[k] ?? keyLabel(k), keyLabel(k).length > 6)}{/each}</div></div>
      {/each}
    {:else if tab === "media"}
      <div class="chips">{#each cat.media as m}{@render chip(`media:${m}`, MEDIA_LABEL[m] ?? m, true)}{/each}</div>
    {:else if tab === "shortcut"}
      <div class="chips">{#each cat.shortcut as m}{@render chip(`shortcut:${m}`, SHORTCUT_LABEL[m] ?? m, true)}{/each}</div>
      <p class="hint m-0">Built into the mouse. Some are made for Windows and may do nothing on Linux.</p>
    {:else if tab === "dpi"}
      <div class="chips">{#each cat.cycle as m}{@render chip(`dpi:${m}`, `${CYCLE_LABEL[m]} DPI`, true)}{/each}</div>
    {:else if tab === "poll"}
      <div class="chips">{#each cat.cycle as m}{@render chip(`poll:${m}`, `${CYCLE_LABEL[m]} rate`, true)}{/each}</div>
    {:else}
      <div class="chips">{@render chip("disable", "Disable button", true)}</div>
      <p class="hint m-0">The left button can't be disabled, so you always have a way to click.</p>
    {/if}
  </div>

  {#if tab === "dpi" || tab === "poll"}
    <p class="hint m-0 border-t-2 border-dashed border-ink/15 pt-3">
      These make a button switch between your {tab === "dpi" ? "DPI steps" : "polling rates"}. To change the {tab === "dpi" ? "DPI values" : "rate"} itself, open
      <button type="button" class="font-extrabold underline" onclick={() => (mouse.section = tab)}>{tab === "dpi" ? "DPI" : "Polling rate"}</button> above.
    </p>
  {/if}
  {/if}
</section>

<style>
  .group { display: grid; gap: .5rem; }
  h4 { margin: 0; font-size: .75rem; font-weight: 900; text-transform: uppercase; letter-spacing: .06em; color: color-mix(in oklab, var(--color-ink) 50%, transparent); }
  .chips { display: grid; grid-template-columns: repeat(auto-fill, minmax(4rem, 1fr)); gap: .5rem; }
  .dim { opacity: .45; pointer-events: none; }
  .dpi-card, .poll-card {
    position: relative; display: grid; gap: .25rem; min-width: 9.5rem; padding: .6rem .8rem; border-radius: 1rem;
    border: 3px solid var(--color-ink); background: var(--color-surface); box-shadow: 3px 3px 0 var(--color-ink);
    transition: transform .12s, box-shadow .12s, background .12s; text-align: left;
  }
  .dpi-card:hover, .poll-card:not(:disabled):hover { transform: translateY(-2px); box-shadow: 4px 5px 0 var(--color-ink); }
  .poll-card { min-width: 8.5rem; cursor: pointer; }
  .dpi-on { background: var(--color-sun); color: var(--color-coal); }
  .dpi-input {
    width: 6.4rem; padding: 0; -moz-appearance: textfield; appearance: textfield; border: 0; border-bottom: 2px dashed currentColor; background: transparent; color: inherit;
    font-size: 1.6rem; font-weight: 900; font-variant-numeric: tabular-nums; outline: none;
  }
  .dpi-input:focus { border-bottom-style: solid; }
  .dpi-input::-webkit-inner-spin-button, .dpi-input::-webkit-outer-spin-button { -webkit-appearance: none; margin: 0; }
  .dpi-add {
    display: grid; place-items: center; gap: .2rem; min-width: 7rem; border: 3px dashed color-mix(in oklab, var(--color-ink) 40%, transparent);
    border-radius: 1rem; font-size: .8rem; font-weight: 800; color: color-mix(in oklab, var(--color-ink) 60%, transparent);
  }
  .dpi-add:not(:disabled):hover { border-color: var(--color-ink); color: var(--color-ink); }
  .chip {
    display: inline-flex; align-items: center; justify-content: center; min-height: 2.6rem; padding: .3rem .5rem;
    border: 2px solid var(--color-ink); border-radius: .8rem; background: var(--color-surface);
    box-shadow: 2px 2px 0 var(--color-ink); font-size: .85rem; font-weight: 800; text-align: center;
    transition: transform .12s, box-shadow .12s, background .12s;
  }
  .chip:not(:disabled):hover { transform: translateY(-2px); box-shadow: 3px 4px 0 var(--color-ink); background: var(--tab-tint); }
  .chip:not(:disabled):active { transform: translateY(1px); box-shadow: 1px 1px 0 var(--color-ink); }
  .chip:disabled { cursor: not-allowed; }
  .step { padding: .2rem .6rem; border: 2px solid var(--color-ink); border-radius: .6rem; background: var(--color-surface); font-weight: 800; font-size: .85rem; font-variant-numeric: tabular-nums; color: color-mix(in oklab, var(--color-ink) 55%, transparent); }
  .step-on { background: var(--color-sun); color: var(--color-coal); box-shadow: 2px 2px 0 var(--color-ink); }
  .chip-on, .chip-on:not(:disabled):hover { background: var(--color-sun); color: var(--color-coal); }
</style>
