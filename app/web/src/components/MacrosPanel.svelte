<script>
  import { Plus, Circle, Square, Trash2, Timer, Type, Keyboard, ArrowDownToLine, ArrowUpFromLine, ChevronUp, ChevronDown,
           X, Code, Sparkles, MousePointerClick, Save, ArrowRight, Wand2 } from "@lucide/svelte";
  import { app, act, load } from "../lib/store.svelte.js";
  import { codeToName, keyLabel } from "../lib/labels.js";
  import { step, stepsToSpec, specToSteps, eventsToSteps, parseEvents, stepLabel, eventCount, macroBytes,
           MACRO_BYTES, TEMPLATES } from "../lib/macro.js";
  import KeyCapture from "./KeyCapture.svelte";

  const KIND = {
    text: { label: "Type text", icon: Type, color: "#ffd23f", help: "Types these characters, like you would." },
    keys: { label: "Press keys", icon: Keyboard, color: "#19d3c5", help: "Presses a key, or several together (a shortcut)." },
    wait: { label: "Wait", icon: Timer, color: "#e7e1f2", help: "Pauses before the next step." },
    down: { label: "Hold down", icon: ArrowDownToLine, color: "#b79bff", help: "Keeps a key pressed until a Release step." },
    up: { label: "Release", icon: ArrowUpFromLine, color: "#ff8cc8", help: "Lets go of a held key." },
  };
  const BADGE = ["#ffd23f", "#19d3c5", "#ff3ea5", "#a8ec00", "#ff7a1a", "#8b5cff"];

  let editing = $state(null);     // macro id being edited, or null for a new one
  let name = $state("");
  let steps = $state([]);
  let focusId = $state(null);     // step to focus after adding it
  let busy = $state(false);
  let saved = $state(null);       // id just saved, to offer "put it on a key"
  let rec = $state(null);         // { events, t } while recording
  let textMode = $state(false);
  let specText = $state("");
  let showMore = $state(false);

  const macros = $derived(app.state.macros);
  const isLast = $derived(editing !== null && editing === macros.length - 1);

  // which keys play a macro
  function keysFor(id) {
    const out = [];
    for (const layer of ["base", "fn"])
      for (const [k, v] of Object.entries(app.state.layers[layer]))
        if (v.action.startsWith(`macro:${id}:`)) out.push((layer === "fn" ? "Fn + " : "") + keyLabel(k));
    return out;
  }
  const savedSteps = (m) => eventsToSteps(parseEvents(m.events));

  // memory: every macro shares 512 bytes on the keyboard
  const used = $derived.by(() => {
    let b = 0;
    for (const m of macros) if (m.id !== editing) b += macroBytes(m.name, parseEvents(m.events).length);
    return b + (steps.length ? macroBytes(name, eventCount(steps)) : 0);
  });
  const pct = $derived(Math.min(100, Math.round((used / MACRO_BYTES) * 100)));

  const problem = $derived.by(() => {
    if (!steps.length) return "Add at least one step.";
    if (steps[0].kind === "wait") return "A macro can't start with a wait. Move it after another step.";
    if (steps.some((s) => s.kind === "text" && !s.text)) return "One of the “Type text” steps is empty.";
    if (steps.some((s) => s.kind === "keys" && !s.keys)) return "One of the “Press keys” steps has no keys yet.";
    if (steps.some((s) => (s.kind === "down" || s.kind === "up") && !s.key)) return "Pick a key for every Hold / Release step.";
    if (used > MACRO_BYTES) return "This is too long for the keyboard's memory. Remove some steps or text.";
    return "";
  });

  function open(m) { stopRec(false); editing = m.id; name = m.name; steps = savedSteps(m); saved = null; textMode = false; }
  function fresh(t) {
    stopRec(false);
    editing = null; saved = null; textMode = false;
    name = t ? t.name : "";
    steps = t ? t.steps() : [];
  }

  function add(kind) {
    const s = step(kind, kind === "text" ? { text: "" } : kind === "keys" ? { keys: "" } : kind === "wait" ? { ms: 200 } : { key: "" });
    steps.push(s);
    focusId = s.id;
    showMore = false;
  }
  function move(i, d) { const [s] = steps.splice(i, 1); steps.splice(i + d, 0, s); }
  function remove(i) { steps.splice(i, 1); }

  function toText() { specText = stepsToSpec(steps); textMode = true; }
  function fromText() { steps = specToSteps(specText); textMode = false; }

  async function save() {
    if (textMode) fromText();
    if (problem) return;
    const id = editing ?? macros.length;
    busy = true;
    try {
      await act("macro", { op: "set", id, spec: stepsToSpec(steps), name: name.trim() || `Macro ${id + 1}` }, "Macro saved to the keyboard");
      editing = id; saved = id;
      await load();
    } catch {} finally { busy = false; }
  }
  async function del() {
    if (!confirm(`Delete “${name}”? Keys that play it will do nothing.`)) return;
    busy = true;
    try { await act("macro", { op: "delete", id: editing }, "Macro deleted"); fresh(); await load(); }
    catch {} finally { busy = false; }
  }
  function putOnKey() {
    app.assignMacro = saved;
    app.selectedKey = null;
    app.tab = "keys";
  }

  // recording: real key presses and their timing turn into steps
  function onRec(e) {
    e.preventDefault();
    e.stopPropagation();
    const n = codeToName(e.code);
    if (!n || e.repeat) return;
    const now = performance.now();
    const ev = rec.events;
    if (ev.length) ev[ev.length - 1].delay = Math.round(now - rec.t);
    rec.t = now;
    ev.push({ name: n, down: e.type === "keydown", delay: 0 });
  }
  function startRec(e) {
    e.currentTarget.blur();
    textMode = false;
    rec = { events: [], t: 0 };
    window.addEventListener("keydown", onRec, true);
    window.addEventListener("keyup", onRec, true);
  }
  function stopRec(apply = true) {
    if (!rec) return;
    window.removeEventListener("keydown", onRec, true);
    window.removeEventListener("keyup", onRec, true);
    if (apply && rec.events.length) steps.push(...eventsToSteps(rec.events, 350));
    rec = null;
  }
  const live = $derived(rec ? eventsToSteps(rec.events, 350) : []);
  $effect(() => () => stopRec(false));
</script>

<div class="grid items-start gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(360px,1.25fr)] xl:contents">
  <!-- left: how it works, your macros, examples -->
  <section class="area-list grid gap-6">
    <ol class="m-0 grid list-none grid-cols-3 gap-3 p-0 max-[720px]:grid-cols-1" aria-label="How macros work">
      {#each [
        { n: 1, t: "Build the steps", d: "Text to type, keys to press, pauses.", c: "#ffd23f" },
        { n: 2, t: "Save to keyboard", d: "It's stored on the F75 itself.", c: "#19d3c5" },
        { n: 3, t: "Put it on a key", d: "Pick which key plays it.", c: "#ff3ea5" },
      ] as s (s.n)}
        <li class="flex items-start gap-3 rounded-2xl border-[3px] border-ink bg-surface px-3 py-2.5 shadow-pop-sm">
          <span class="grid size-8 shrink-0 place-items-center rounded-full border-[2.5px] border-ink font-black text-coal" style:background={s.c}>{s.n}</span>
          <span class="grid leading-tight"><strong class="text-sm font-extrabold">{s.t}</strong><small class="text-xs text-ink/60">{s.d}</small></span>
        </li>
      {/each}
    </ol>

    <div class="grid gap-3">
      <div class="flex items-center justify-between gap-4">
        <h2>Your macros</h2>
        <button class="btn btn-sun" onclick={() => fresh()}><Plus size={16} strokeWidth={3} /> New macro</button>
      </div>
      {#if macros.length}
        <ul class="stagger m-0 grid list-none gap-3 p-0 xl:grid-cols-[repeat(auto-fill,minmax(300px,1fr))]">
          {#each macros as m (m.id)}
            {@const on = editing === m.id}
            {@const ks = keysFor(m.id)}
            {@const ss = savedSteps(m)}
            <li>
              <button class="grid w-full gap-2 rounded-2xl border-[3px] border-ink px-3 py-2.5 text-left transition-all
                             {on ? 'shadow-pop -translate-y-0.5' : 'bg-surface shadow-pop-sm hover:-translate-y-0.5 hover:shadow-pop'}"
                      style:background={on ? "var(--tab-tint)" : null} aria-current={on} onclick={() => open(m)}>
                <span class="flex items-center gap-3">
                  <span class="grid size-9 shrink-0 place-items-center rounded-xl border-[2.5px] border-ink font-black text-coal"
                        style:background={BADGE[m.id % BADGE.length]}>{m.id + 1}</span>
                  <strong class="min-w-0 flex-1 truncate font-extrabold">{m.name}</strong>
                  {#if ks.length}
                    <span class="sticker shrink-0 bg-lime px-2 py-0.5 text-[.68rem]">on {ks.join(", ")}</span>
                  {:else}
                    <span class="sticker shrink-0 bg-surface px-2 py-0.5 text-[.68rem] text-ink/60">not on a key</span>
                  {/if}
                </span>
                <span class="flex flex-wrap gap-1">
                  {#each ss.slice(0, 4) as s (s.id)}
                    <span class="max-w-40 truncate rounded-md border-2 border-ink px-1.5 text-[.7rem] font-bold text-coal" style:background={KIND[s.kind].color}>{stepLabel(s)}</span>
                  {/each}
                  {#if ss.length > 4}<span class="text-[.7rem] font-bold text-ink/50">+{ss.length - 4} more</span>{/if}
                </span>
              </button>
            </li>
          {/each}
        </ul>
      {:else}
        <p class="hint rounded-2xl border-[3px] border-dashed border-ink/30 bg-surface/60 px-4 py-3">
          You don't have any macros yet. Start from an example below, or press <strong>New macro</strong>.
        </p>
      {/if}
    </div>

    <div class="grid gap-3">
      <h3 class="flex items-center gap-1.5"><Wand2 size={14} strokeWidth={3} /> Start from an example</h3>
      <div class="stagger grid grid-cols-[repeat(auto-fill,minmax(200px,1fr))] gap-3">
        {#each TEMPLATES as t (t.name)}
          <button class="grid gap-0.5 rounded-2xl border-[3px] border-dashed border-ink/50 bg-surface/70 px-3 py-2.5 text-left transition-all
                         hover:-translate-y-0.5 hover:border-solid hover:border-ink hover:shadow-pop" onclick={() => fresh(t)}>
            <strong class="text-sm font-extrabold">{t.name}</strong>
            <small class="text-xs text-ink/55">{t.hint}</small>
          </button>
        {/each}
      </div>
    </div>

    <div class="grid gap-1.5">
      <div class="flex justify-between text-xs font-extrabold"><span class="tracking-[.12em] text-ink/60">KEYBOARD MACRO MEMORY</span><span>{pct}% used</span></div>
      <div class="h-3.5 overflow-hidden rounded-full border-[2.5px] border-ink bg-surface">
        <div class="h-full transition-all duration-300" style:width={pct + "%"}
             style:background={pct > 90 ? "var(--color-cherry)" : pct > 70 ? "var(--color-tang)" : "var(--color-lime)"}></div>
      </div>
    </div>
  </section>

  <!-- right: the editor -->
  <section class="card area-aside grid gap-5" style:background="linear-gradient(160deg, var(--color-surface) 55%, var(--tab-tint))">
    {#if saved !== null && !rec}
      <div class="grid gap-2 rounded-2xl border-[3px] border-ink bg-lime p-3.5 shadow-pop-sm animate-pop-in">
        <strong class="flex items-center gap-2 font-black"><Sparkles size={18} strokeWidth={2.6} /> Saved to the keyboard!</strong>
        {#if keysFor(saved).length}
          <span class="text-sm font-semibold">Press {keysFor(saved).join(" or ")} to play it.</span>
        {:else}
          <span class="text-sm font-semibold">Last step: choose which key plays it.</span>
          <button class="btn bg-white text-coal justify-self-start" onclick={putOnKey}>Put it on a key <ArrowRight size={16} strokeWidth={3} /></button>
        {/if}
      </div>
    {/if}

    <div class="flex items-center justify-between gap-3">
      <h2 class="text-2xl font-black">{editing === null ? "New macro" : "Edit macro"}</h2>
      {#if !rec}
        <button class="sticker bg-surface text-ink hover:bg-ink/5" onclick={() => (textMode ? fromText() : toText())}
                title="For power users: write the steps as text">
          <Code size={13} strokeWidth={3} /> {textMode ? "Back to steps" : "Edit as text"}
        </button>
      {/if}
    </div>

    <label class="field"><span>Name</span>
      <input class="input" maxlength="30" placeholder="e.g. Copy and paste" bind:value={name}></label>

    <div class="grid gap-2.5">
      <h3>Steps <span class="normal-case tracking-normal text-ink/45">· played from top to bottom</span></h3>

      {#if rec}
        <div class="grid gap-3 rounded-2xl border-[3px] border-dashed border-cherry bg-cherry/10 p-4" role="status">
          <p class="m-0 flex items-center gap-2 font-extrabold text-cherry">
            <span class="size-3 animate-pulse rounded-full bg-cherry"></span> Recording… type on your keyboard now
          </p>
          {#if live.length}
            <div class="flex flex-wrap gap-1.5">
              {#each live as s (s.id)}
                <span class="rounded-lg border-2 border-ink px-2 py-0.5 text-xs font-extrabold text-coal shadow-pop-sm" style:background={KIND[s.kind].color}>{stepLabel(s)}</span>
              {/each}
            </div>
          {:else}
            <p class="hint">Every key you press is captured, including shortcuts. Press <strong>Stop</strong> when you're done.</p>
          {/if}
          <button class="btn btn-danger justify-self-start" onclick={() => stopRec()}><Square size={14} fill="currentColor" /> Stop recording</button>
        </div>
      {:else if textMode}
        <textarea class="input" rows="4" spellcheck="false" placeholder={'"hello" lctrl+c 200ms lctrl+v'} bind:value={specText}></textarea>
        <p class="hint text-xs leading-7">Text in quotes <kbd>"hello"</kbd> · shortcuts <kbd>lctrl+v</kbd> · pauses <kbd>200ms</kbd> ·
          hold / release <kbd>+lshift</kbd> <kbd>-lshift</kbd></p>
      {:else}
        {#if steps.length}
          <ol class="m-0 grid list-none gap-2 p-0">
            {#each steps as s, i (s.id)}
              {@const K = KIND[s.kind]}
              <li class="flex items-center gap-2.5 rounded-2xl border-[3px] border-ink bg-surface py-2 pl-2 pr-1.5 shadow-pop-sm animate-pop-in">
                <span class="grid size-9 shrink-0 place-items-center rounded-xl border-[2.5px] border-ink text-coal" style:background={K.color} title={K.help}>
                  <K.icon size={17} strokeWidth={2.6} />
                </span>
                <div class="grid min-w-0 flex-1 gap-1">
                  <span class="text-[.68rem] font-extrabold uppercase tracking-[.12em] text-ink/55">{i + 1}. {K.label}</span>
                  {#if s.kind === "text"}
                    <!-- svelte-ignore a11y_autofocus -->
                    <input class="input py-2" placeholder="What should it type?" aria-label="Text to type" bind:value={s.text} autofocus={focusId === s.id}>
                  {:else if s.kind === "keys"}
                    <KeyCapture bind:value={s.keys} label="Keys to press" autofocus={focusId === s.id} />
                  {:else if s.kind === "wait"}
                    <div class="flex flex-wrap items-center gap-1.5">
                      <input class="input w-24 py-2" type="number" min="1" max="60000" aria-label="Pause in milliseconds" bind:value={s.ms}>
                      <span class="text-sm font-bold text-ink/60">ms</span>
                      {#each [100, 500, 1000] as v}
                        <button class="sticker px-2 py-0.5 {s.ms === v ? 'bg-sun' : 'bg-cream text-ink'}" onclick={() => (s.ms = v)}>{v >= 1000 ? v / 1000 + " s" : v + " ms"}</button>
                      {/each}
                    </div>
                  {:else}
                    <KeyCapture bind:value={s.key} single label={K.label} autofocus={focusId === s.id} />
                  {/if}
                </div>
                <div class="grid shrink-0 gap-0.5">
                  <button class="grid size-7 place-items-center rounded-lg hover:bg-ink/10 disabled:opacity-25" disabled={i === 0} onclick={() => move(i, -1)} aria-label="Move up"><ChevronUp size={16} strokeWidth={3} /></button>
                  <button class="grid size-7 place-items-center rounded-lg hover:bg-ink/10 disabled:opacity-25" disabled={i === steps.length - 1} onclick={() => move(i, 1)} aria-label="Move down"><ChevronDown size={16} strokeWidth={3} /></button>
                </div>
                <button class="grid size-8 shrink-0 place-items-center rounded-lg text-ink/50 hover:bg-cherry hover:text-white" onclick={() => remove(i)} aria-label="Remove step"><X size={17} strokeWidth={3} /></button>
              </li>
            {/each}
          </ol>
        {:else}
          <div class="grid justify-items-center gap-1 rounded-2xl border-[3px] border-dashed border-ink/30 px-4 py-5 text-center">
            <MousePointerClick size={24} strokeWidth={2.4} class="text-ink/45" />
            <p class="m-0 font-extrabold">No steps yet</p>
            <p class="hint text-xs">Add steps with the buttons below, or record them by typing.</p>
          </div>
        {/if}

        <div class="grid gap-2">
          <div class="flex flex-wrap gap-2">
            {#each ["text", "keys", "wait"] as k}
              {@const K = KIND[k]}
              <button class="btn px-3 py-1.5 text-coal" style:background={K.color} onclick={() => add(k)}><Plus size={14} strokeWidth={3} /> {K.label}</button>
            {/each}
            <button class="btn btn-quiet px-3 py-1.5" onclick={startRec}><Circle size={12} fill="#ff3b3b" class="text-cherry" /> Record</button>
          </div>
          <div class="flex flex-wrap items-center gap-2 text-xs">
            <button class="link text-xs" onclick={() => (showMore = !showMore)}>{showMore ? "Fewer options" : "More: hold / release a key"}</button>
            {#if showMore}
              <button class="sticker text-coal" style:background={KIND.down.color} onclick={() => add("down")}><Plus size={12} strokeWidth={3} /> Hold down</button>
              <button class="sticker text-coal" style:background={KIND.up.color} onclick={() => add("up")}><Plus size={12} strokeWidth={3} /> Release</button>
            {/if}
          </div>
        </div>
      {/if}
    </div>

    {#if !rec}
      {#if problem && steps.length && !textMode}
        <p class="m-0 rounded-xl border-2 border-ink bg-sun/30 px-3 py-2 text-sm font-semibold">{problem}</p>
      {/if}
      <div class="flex flex-wrap items-center gap-3">
        <button class="btn btn-primary" disabled={busy || (!textMode && !!problem)} onclick={save}>
          <Save size={16} strokeWidth={2.6} /> {editing === null ? "Save to keyboard" : "Save changes"}
        </button>
        {#if editing !== null}
          <button class="btn btn-danger" disabled={busy || !isLast} onclick={del}
                  title={isLast ? "" : "Only the newest macro can be deleted, so keys using the others keep working"}>
            <Trash2 size={16} strokeWidth={2.8} /> Delete
          </button>
        {/if}
      </div>
      {#if editing !== null && !isLast}
        <p class="hint -mt-2 text-xs">Only the newest macro can be deleted (so keys using the others keep working).</p>
      {/if}
    {/if}
  </section>
</div>
