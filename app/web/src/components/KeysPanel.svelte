<script>
  import { Keyboard, Music, Workflow, Ban, RotateCcw, MousePointerClick, X } from "@lucide/svelte";
  import { app, act, load } from "../lib/store.svelte.js";
  import { keyLabel, describe, codeToName, MODS, MEDIA_LABEL } from "../lib/labels.js";
  import Segmented from "./Segmented.svelte";

  const LAYERS = [{ value: "base", label: "Normal" }, { value: "fn", label: "While holding Fn" }];
  const TYPES = [
    { value: "key", label: "Key", icon: Keyboard },
    { value: "media", label: "Media", icon: Music },
    { value: "macro", label: "Macro", icon: Workflow },
    { value: "disable", label: "Off", icon: Ban },
  ];

  const layerKeys = $derived(app.state.layers[app.layer]);
  const changed = $derived(Object.entries(layerKeys).filter(([, v]) => v.changed).map(([k]) => k));
  const info = $derived(app.selectedKey ? layerKeys[app.selectedKey] : null);
  const protectedKey = $derived(app.layer === "base" && app.selectedKey === "fn");

  let type = $state("key");
  let captured = $state("");
  let listening = $state(false);
  let media = $state("play");
  let macroId = $state("");
  let macroMode = $state("times");
  let times = $state(1);
  let busy = $state(false);
  let presetFor = "";

  // Fill the editor from the key's current action whenever another key/layer is picked.
  $effect(() => {
    const id = `${app.layer}:${app.selectedKey}`;
    if (!info || id === presetFor) return;
    presetFor = id;
    const a = info.action;
    if (a.startsWith("macro:")) {
      const [, mid, mode, n] = a.split(":");
      type = "macro"; macroId = mid; macroMode = mode; times = +(n || 1);
    } else if (MEDIA_LABEL[a]) { type = "media"; media = a; }
    else if (a === "disabled") type = "disable";
    else { type = "key"; captured = a.startsWith("special") || a === "fn" ? "" : a; }
    if (!macroId && app.state.macros.length) macroId = "0";
    if (app.assignMacro !== null) { type = "macro"; macroId = String(app.assignMacro); macroMode = "times"; times = 1; }
  });
  const assigning = $derived(app.assignMacro !== null ? app.state.macros.find((m) => m.id === app.assignMacro) : null);

  const held = new Set();
  function keydown(e) {
    if (e.key === "Tab" && !held.size) return;
    e.preventDefault();
    const n = codeToName(e.code);
    if (!n || e.repeat) return;
    if (!held.size) captured = "";
    held.add(n);
    const mods = MODS.filter((m) => held.has(m));
    const rest = [...held].filter((x) => !MODS.includes(x)).slice(0, 2);
    captured = [...mods, ...rest].join("+");
  }
  function keyup(e) { const n = codeToName(e.code); if (n) held.delete(n); }

  async function save(action, msg) {
    busy = true;
    try {
      await act("remap", { layer: app.layer, key: app.selectedKey, action }, msg);
      presetFor = "";
      if (action.startsWith("macro:")) app.assignMacro = null;
      await load();
    } catch { /* toast shown */ } finally { busy = false; }
  }
  function submit() {
    let action;
    if (type === "key") action = captured;
    else if (type === "media") action = media;
    else if (type === "disable") action = "disable";
    else action = `macro:${macroId}:${macroMode}` + (macroMode === "times" ? `:${Math.max(1, Math.min(255, +times || 1))}` : "");
    save(action, `${keyLabel(app.selectedKey)} saved`);
  }
  async function resetAll() {
    if (!confirm("Reset every key on both layers to the factory layout? Macros are kept.")) return;
    busy = true;
    try { await act("reset-keys", {}, "All keys reset to factory"); presetFor = ""; await load(); }
    catch {} finally { busy = false; }
  }
  const canSave = $derived(
    !busy && !protectedKey &&
    (type === "key" ? !!captured : type === "macro" ? macroId !== "" && app.state.macros.length > 0 : true));
</script>

<div class="grid items-start gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(320px,1.15fr)] xl:contents">
  <section class="area-list grid justify-items-start gap-6">
    <div class="grid gap-2.5">
      <h3>Layer</h3>
      <Segmented options={LAYERS} bind:value={app.layer} label="Layer" />
    </div>
    <div class="grid w-full gap-2.5">
      <h3>Changed on this layer {#if changed.length}<span class="ml-1 rounded-full border-2 border-ink bg-sun px-2 text-coal">{changed.length}</span>{/if}</h3>
      {#if changed.length}
        <div class="stagger grid w-full gap-2.5 xl:grid-cols-[repeat(auto-fill,minmax(260px,1fr))]">
          {#each changed as k (k)}
            {@const on = app.selectedKey === k}
            <button class="flex items-center gap-2.5 rounded-2xl border-[3px] border-ink px-3 py-2 text-left text-sm font-semibold transition-all
                           {on ? 'bg-sun text-coal shadow-pop -translate-y-0.5' : 'bg-surface shadow-pop-sm hover:-translate-y-0.5 hover:shadow-pop'}"
                    onclick={() => (app.selectedKey = k)}>
              <span class="rounded-lg border-2 border-ink px-2 py-0.5 font-black text-white shadow-pop-sm" style:background="var(--tab)">{keyLabel(k)}</span>
              <span class="text-xs font-extrabold uppercase tracking-wider text-ink/45">does</span>
              <span class="min-w-0 truncate font-bold">{describe(layerKeys[k].action, app.state.macros)}</span>
            </button>
          {/each}
        </div>
      {:else}
        <p class="hint rounded-2xl border-[3px] border-dashed border-ink/30 bg-surface/60 px-4 py-3">Every key does what's printed on it.</p>
      {/if}
    </div>
    <button class="btn btn-danger" disabled={busy} onclick={resetAll}><RotateCcw size={16} strokeWidth={2.8} /> Reset all keys to factory</button>
  </section>

  <section class="card area-aside grid gap-5" style:background="linear-gradient(160deg, var(--color-surface) 55%, var(--tab-tint))">
    {#if assigning}
      <div class="flex items-start gap-3 rounded-2xl border-[3px] border-ink bg-sun p-3 shadow-pop-sm animate-pop-in">
        <Workflow size={20} strokeWidth={2.6} class="mt-0.5 shrink-0" />
        <div class="grid flex-1 gap-0.5">
          <strong class="font-black">Putting “{assigning.name}” on a key</strong>
          <span class="text-sm font-semibold">{info ? "Check the settings below, then press Save key." : "Click the key on the keyboard that should play it."}</span>
        </div>
        <button class="grid size-7 shrink-0 place-items-center rounded-lg hover:bg-coal/10" aria-label="Cancel" onclick={() => (app.assignMacro = null)}><X size={16} strokeWidth={3} /></button>
      </div>
    {/if}
    {#if !info}
      <div class="grid justify-items-center gap-2 px-4 py-8 text-center">
        <div class="mb-2 grid size-16 rotate-6 animate-bounce place-items-center rounded-2xl border-[3px] border-ink bg-sun shadow-pop">
          <MousePointerClick size={30} strokeWidth={2.4} />
        </div>
        <h2 class="text-2xl font-black">Pick a key!</h2>
        <p class="hint">Click a key on the keyboard. Keys you've changed glow in blue.</p>
      </div>
    {:else}
      <header class="flex items-center gap-4">
        <span class="-rotate-3 whitespace-nowrap rounded-2xl border-[3px] border-ink bg-sun px-4 py-3 text-xl font-black shadow-pop">
          {app.layer === "fn" ? "Fn + " : ""}{keyLabel(app.selectedKey)}
        </span>
        <div class="min-w-0">
          <p class="m-0 text-lg font-extrabold leading-tight">{describe(info.action, app.state.macros)}</p>
          {#if info.changed}<p class="hint mt-0.5">Factory setting: {describe(info.default, app.state.macros)}</p>{/if}
        </div>
      </header>

      {#if protectedKey}
        <p class="hint rounded-2xl border-[3px] border-ink bg-sun/25 px-4 py-3">Fn can't be changed here, or you would lose the Fn layer and the built-in shortcuts.</p>
      {:else}
        <Segmented options={TYPES} bind:value={type} label="What the key does" />

        <div class="grid gap-3">
          {#if type === "key"}
            <label class="field">
              <span>Press the new key or shortcut</span>
              <input class="input cursor-pointer text-lg font-black caret-transparent {listening ? 'animate-pulse bg-sun/30' : ''}" readonly
                     style:box-shadow={listening ? "4px 4px 0 var(--tab)" : null}
                     value={captured ? captured.split("+").map(keyLabel).join(" + ") : ""}
                     placeholder={listening ? "Press keys now…" : "Click here, then press keys"}
                     onkeydown={keydown} onkeyup={keyup}
                     onfocus={() => { held.clear(); listening = true; }}
                     onblur={() => { held.clear(); listening = false; }}>
            </label>
            <p class="hint">Hold keys together for a shortcut, like <kbd>Ctrl</kbd> <kbd>Shift</kbd> <kbd>T</kbd>.</p>
          {:else if type === "media"}
            <label class="field"><span>Media action</span>
              <select class="input" bind:value={media}>
                {#each app.catalog.media as m}<option value={m}>{MEDIA_LABEL[m] ?? m}</option>{/each}
              </select>
            </label>
          {:else if type === "macro"}
            {#if app.state.macros.length}
              <label class="field"><span>Macro</span>
                <select class="input" bind:value={macroId}>
                  {#each app.state.macros as m (m.id)}<option value={String(m.id)}>{m.name}</option>{/each}
                </select>
              </label>
              <label class="field"><span>Plays</span>
                <select class="input" bind:value={macroMode}>
                  <option value="times">A set number of times</option>
                  <option value="hold">Over and over while held</option>
                  <option value="toggle">Over and over until another key is pressed</option>
                </select>
              </label>
              {#if macroMode === "times"}
                <label class="field"><span>Times</span>
                  <input class="input" type="number" min="1" max="255" bind:value={times}></label>
              {/if}
            {:else}
              <p class="hint">No macros yet. <button class="link" onclick={() => (app.tab = "macros")}>Create one in Macros.</button></p>
            {/if}
          {:else}
            <p class="hint">The key will do nothing when pressed.</p>
          {/if}
        </div>

        <div class="flex flex-wrap gap-3">
          <button class="btn btn-primary" disabled={!canSave} onclick={submit}>Save key</button>
          <button class="btn btn-line" disabled={busy || !info.changed} onclick={() => save("default", `${keyLabel(app.selectedKey)} restored`)}>
            <RotateCcw size={16} strokeWidth={2.8} /> Factory setting
          </button>
        </div>
      {/if}
    {/if}
  </section>
</div>
