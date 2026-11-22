<script>
  import { onDestroy } from "svelte";
  import {
    Search, X, Pin, ArrowRight, TriangleAlert, Info, Bluetooth, RadioTower, Usb, BatteryMedium, Eye, RotateCcw,
    Wrench, ChevronDown, Mail, ShieldCheck, ExternalLink, Gamepad2, Briefcase, Disc3,
  } from "@lucide/svelte";
  import { app } from "../lib/store.svelte.js";
  import { GROUPS, KNOB, OS_MODES, HOWTO, SPECS, SUPPORT, keyName } from "../lib/manual.js";
  import Segmented from "./Segmented.svelte";

  const TAB_NAME = { power: "Power", backups: "Backups", lighting: "Lighting" };
  const HOWTO_ICON = { bt: Bluetooth, "24g": RadioTower, wired: Usb, battery: BatteryMedium, fnkey: Eye, reset: RotateCcw, switches: Wrench };
  const KNOB_ICON = { gaming: Gamepad2, office: Briefcase };

  let query = $state("");
  let pinned = $state(null);   // { id, keys }: stays lit after a click
  let open = $state("bt");
  const g = app.guide;

  const os = $derived(OS_MODES.find((m) => m.id === g.os));
  const needle = $derived(query.trim().toLowerCase());
  const hit = (...texts) => !needle || texts.join(" ").toLowerCase().includes(needle);
  const comboText = (keys) => keys.map(keyName).join(" + ");
  const usesKey = (keys) => !g.key || keys.includes(g.key);

  const groups = $derived(GROUPS.map((gr) => ({
    ...gr, items: gr.items.filter((it) => usesKey(it.keys) && hit(comboText(it.keys), it.what, it.tip ?? "", gr.title)),
  })).filter((gr) => gr.items.length));
  const fkeys = $derived(os.plain.map((plain, i) => ({ k: "f" + (i + 1), plain, fn: os.fn[i] }))
    .filter((f) => usesKey([f.k, "fn"]) && hit(f.k, f.plain, f.fn, "f-keys function row")));
  const knob = $derived(KNOB.filter((m) => usesKey(["wheel"]) && hit("knob", m.title, m.light, ...m.actions.flat())));
  const howtos = $derived(HOWTO.filter((h) => (!g.key || h.keys.includes(g.key)) && hit(h.title, ...h.steps, h.note ?? "")));
  const nothing = $derived(!groups.length && !fkeys.length && !knob.length && !howtos.length);
  const rowId = (gr, it) => gr.id + ":" + it.what;
  // ids of everything that can be pinned and is on screen right now
  const visible = $derived(new Set([
    ...groups.flatMap((gr) => gr.items.map((it) => rowId(gr, it))),
    ...fkeys.flatMap((f) => [f.k, "fn" + f.k]), ...knob.map((m) => m.id),
  ]));

  function show(keys) { g.keys = keys; }
  function rest() { g.keys = pinned?.keys ?? []; }
  function pin(id, keys) {
    pinned = pinned?.id === id ? null : { id, keys };
    rest();
  }
  const lit = (id) => pinned?.id === id;
  // a search or key filter can hide whatever was pointed at or pinned: don't leave its keys lit
  $effect(() => {
    if (pinned && !visible.has(pinned.id)) pinned = null;
    g.keys = pinned?.keys ?? [];
  });
  onDestroy(() => { g.keys = []; g.key = null; });

  const hover = (keys) => ({ onpointerenter: () => show(keys), onpointerleave: rest, onfocus: () => show(keys), onblur: rest });
</script>

{#snippet combo(keys)}
  <span class="flex shrink-0 items-center gap-1">
    {#each keys as k, i (k)}
      {#if i}<span class="text-xs font-black text-ink/40">+</span>{/if}
      <kbd class:fnkey={k === "fn"}>{keyName(k)}</kbd>
    {/each}
  </span>
{/snippet}

{#snippet goTo(tab)}
  <button class="link inline-flex items-center gap-1 text-sm" onclick={() => (app.tab = tab)}>
    {TAB_NAME[tab]} tab <ArrowRight size={14} strokeWidth={3} />
  </button>
{/snippet}

<div class="grid items-start gap-8 lg:grid-cols-[minmax(0,1.5fr)_minmax(300px,1fr)] xl:contents">
  <section class="area-list grid content-start gap-6">
    <div class="flex flex-wrap items-center gap-3">
      <label class="relative min-w-[220px] flex-1">
        <Search size={18} strokeWidth={2.8} class="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-ink/50" />
        <input class="input pl-10" type="search" placeholder="Search: pair, brightness, reset…" bind:value={query} aria-label="Search the manual" />
      </label>
      {#if g.key}
        <span class="sticker bg-sun">
          Shortcuts with <kbd class="chip-kbd">{keyName(g.key)}</kbd>
          <button class="-mr-1 grid size-5 place-items-center rounded-full hover:bg-coal/15" aria-label="Show all keys" onclick={() => (g.key = null)}>
            <X size={14} strokeWidth={3} />
          </button>
        </span>
      {:else}
        <p class="hint text-xs">Point at a shortcut to see its keys. Click a key on the keyboard to see what it does.</p>
      {/if}
    </div>

    {#if nothing}
      <p class="hint rounded-2xl border-[3px] border-dashed border-ink/30 bg-surface/60 px-4 py-3">
        Nothing in the manual matches{needle ? ` “${query.trim()}”` : ""}{g.key ? ` for ${keyName(g.key)}` : ""}.
      </p>
    {/if}

    {#if groups.length}
      <div class="stagger grid grid-cols-[repeat(auto-fill,minmax(310px,1fr))] items-start gap-4">
        {#each groups as gr (gr.id)}
          <div class="overflow-hidden rounded-2xl border-[3px] border-ink bg-surface shadow-pop-sm">
            <h3 class="flex items-center gap-2 border-b-[3px] border-ink px-3.5 py-2" style:background={gr.color} style:color={gr.text ?? "var(--color-coal)"}>{gr.title}</h3>
            <ul class="m-0 grid list-none p-1.5">
              {#each gr.items as it (it.what)}
                {@const id = rowId(gr, it)}
                <li class="row grid gap-1 rounded-xl px-2 py-1.5" class:on={lit(id)}>
                  <button class="flex w-full items-center gap-3 text-left" {...hover(it.keys)} onclick={() => pin(id, it.keys)}
                          aria-pressed={lit(id)} title="Click to keep these keys lit">
                    {@render combo(it.keys)}
                    <span class="min-w-0 flex-1 font-bold leading-tight">{it.what}</span>
                    {#if lit(id)}<Pin size={14} strokeWidth={3} class="shrink-0" />{/if}
                    {#if it.hold}<span class="badge shrink-0 rounded-md bg-ink/8 px-1.5 py-0.5 text-[.68rem] font-extrabold uppercase tracking-wide text-ink/60">{it.hold}</span>{/if}
                  </button>
                  {#if it.tip || it.goto}
                    <p class="m-0 flex flex-wrap items-center gap-x-2 pl-1 text-xs text-ink/60" class:warn={it.warn}>
                      {#if it.warn}<TriangleAlert size={13} strokeWidth={3} />{/if}
                      {it.tip ?? ""}
                      {#if it.goto}{@render goTo(it.goto)}{/if}
                    </p>
                  {/if}
                </li>
              {/each}
            </ul>
          </div>
        {/each}
      </div>
    {/if}

    {#if fkeys.length}
      <div class="grid gap-3">
        <div class="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2>Function row</h2>
            <p class="hint">What F1–F12 do on their own and with Fn. Switch system mode with {comboText(os.combo)}.</p>
          </div>
          <Segmented label="System mode" options={OS_MODES.map((m) => ({ value: m.id, label: m.label }))} bind:value={g.os} />
        </div>
        <div class="grid grid-cols-[repeat(auto-fill,minmax(132px,1fr))] gap-2.5">
          {#each fkeys as f (f.k)}
            <div class="fcell grid overflow-hidden rounded-xl border-[3px] border-ink bg-surface shadow-pop-sm">
              <button class="grid gap-0.5 px-2.5 pb-1.5 pt-2 text-left" class:on={lit(f.k)} {...hover([f.k])} onclick={() => pin(f.k, [f.k])}>
                <kbd class="justify-self-start">{keyName(f.k)}</kbd>
                <span class="text-[.8rem] font-bold leading-tight">{f.plain}</span>
              </button>
              <button class="grid gap-0.5 border-t-2 border-dashed border-ink/25 bg-cream px-2.5 py-1.5 text-left" class:on={lit("fn" + f.k)}
                      {...hover(["fn", f.k])} onclick={() => pin("fn" + f.k, ["fn", f.k])}>
                <span class="text-[.65rem] font-extrabold uppercase tracking-wider text-ink/50">with Fn</span>
                <span class="text-[.8rem] font-bold leading-tight">{f.fn}</span>
              </button>
            </div>
          {/each}
        </div>
        {#if g.os !== "win"}
          <p class="hint flex items-center gap-1.5 text-xs"><Info size={14} strokeWidth={2.6} /> On Linux, Windows mode is usually the better fit: the keys behave like a normal PC keyboard.</p>
        {/if}
      </div>
    {/if}

    {#if knob.length}
      <div class="grid gap-3">
        <div>
          <h2>The knob</h2>
          <p class="hint">Press and hold the knob for 3–5 seconds to switch between its two modes.</p>
        </div>
        <div class="grid grid-cols-[repeat(auto-fill,minmax(300px,1fr))] gap-3">
          {#each knob as m (m.id)}
            {@const Icon = KNOB_ICON[m.id]}
            <button class="row grid gap-2 rounded-2xl border-[3px] border-ink bg-surface p-3.5 text-left shadow-pop-sm" class:on={lit(m.id)}
                    {...hover(["wheel"])} onclick={() => pin(m.id, ["wheel"])}>
              <span class="flex items-center gap-2">
                <span class="grid size-8 place-items-center rounded-lg border-[2.5px] border-ink bg-sun text-coal"><Icon size={17} strokeWidth={2.6} /></span>
                <span class="grid leading-tight"><strong class="font-black">{m.title}</strong>
                  <span class="text-xs font-semibold text-ink/55">{m.light}</span></span>
              </span>
              <span class="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
                {#each m.actions as [how, what] (how)}
                  <span class="flex items-center gap-1 whitespace-nowrap font-extrabold text-ink/60"><Disc3 size={13} strokeWidth={2.8} /> {how}</span>
                  <span class="font-bold">{what}</span>
                {/each}
              </span>
            </button>
          {/each}
        </div>
      </div>
    {/if}
  </section>

  {#if !needle || howtos.length}
  <aside class="card area-aside grid content-start gap-5" style:background="linear-gradient(160deg, var(--color-surface) 55%, var(--tab-tint))">
    {#if howtos.length}
      <div class="grid gap-2">
        <h2 class="text-2xl font-black">How to</h2>
        {#each howtos as h (h.id)}
          {@const Icon = HOWTO_ICON[h.id]}
          {@const expanded = open === h.id || !!needle}
          <div class="overflow-hidden rounded-2xl border-[3px] border-ink bg-surface transition-shadow" class:shadow-pop={expanded} class:shadow-pop-sm={!expanded}>
            <button class="flex w-full items-center gap-2.5 px-3 py-2.5 text-left font-extrabold" aria-expanded={expanded}
                    {...hover(h.keys)} onclick={() => (open = open === h.id ? null : h.id)}>
              <span class="grid size-8 shrink-0 place-items-center rounded-lg border-[2.5px] border-ink text-white"
                    style:background={h.warn ? "var(--color-cherry)" : "var(--tab)"}><Icon size={16} strokeWidth={2.6} /></span>
              <span class="flex-1">{h.title}</span>
              {#if h.keys.length > 1}{@render combo(h.keys)}{/if}
              <ChevronDown size={18} strokeWidth={3} class="shrink-0 transition-transform {expanded ? 'rotate-180' : ''}" />
            </button>
            {#if expanded}
              <div class="grid gap-2.5 border-t-2 border-dashed border-ink/20 px-3.5 pb-3.5 pt-3">
                <ol class="m-0 grid list-none gap-2 p-0">
                  {#each h.steps as s, i (i)}
                    <li class="flex gap-2.5 text-sm leading-snug">
                      <span class="grid size-6 shrink-0 place-items-center rounded-full border-2 border-ink bg-sun text-xs font-black text-coal">{i + 1}</span>
                      <span class="pt-0.5">{s}</span>
                    </li>
                  {/each}
                </ol>
                {#if h.note}
                  <p class="m-0 flex items-start gap-2 rounded-xl border-2 border-ink px-3 py-2 text-xs font-semibold"
                     class:bg-sun={!h.warn} class:warnbox={h.warn}>
                    {#if h.warn}<TriangleAlert size={15} strokeWidth={2.8} class="mt-px shrink-0" />{:else}<Info size={15} strokeWidth={2.8} class="mt-px shrink-0" />{/if}
                    {h.note}
                  </p>
                {/if}
                {#if h.goto || h.link}
                  <div class="flex flex-wrap gap-x-4 gap-y-1">
                    {#if h.goto}{@render goTo(h.goto)}{/if}
                    {#if h.link}
                      <a class="link inline-flex items-center gap-1 text-sm text-ink" href={h.link[1]} target="_blank" rel="noreferrer">
                        {h.link[0]} <ExternalLink size={13} strokeWidth={3} />
                      </a>
                    {/if}
                  </div>
                {/if}
              </div>
            {/if}
          </div>
        {/each}
      </div>
    {/if}

    {#if !needle}
      <div class="grid gap-2.5 {howtos.length ? 'border-t-[3px] border-dashed border-ink/20 pt-5' : ''}">
        <h3>Specs</h3>
        <dl class="m-0 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-sm">
          {#each SPECS as [k, v] (k)}
            <dt class="font-extrabold text-ink/55">{k}</dt>
            <dd class="m-0 font-semibold">{v}</dd>
          {/each}
        </dl>
      </div>

      <div class="grid gap-2.5 border-t-[3px] border-dashed border-ink/20 pt-5">
        <h3>Help & warranty</h3>
        <p class="m-0 text-sm">{SUPPORT.text}</p>
        <a class="btn btn-line justify-self-start" href={"mailto:" + SUPPORT.email}><Mail size={16} strokeWidth={2.8} /> {SUPPORT.email}</a>
        <p class="m-0 flex items-start gap-2 text-xs text-ink/60"><ShieldCheck size={15} strokeWidth={2.6} class="mt-px shrink-0" /> {SUPPORT.warranty}</p>
        <p class="m-0 text-xs text-ink/45">From the EPOMAKER x AULA F75 quick start guide.</p>
      </div>
    {/if}
  </aside>
  {/if}
</div>

<style>
  .row { transition: background-color .12s, translate .12s, box-shadow .12s; }
  .row:has(> button:hover), .row:has(> button:focus-visible), button.row:hover, button.row:focus-visible {
    background: color-mix(in oklab, var(--tab) 14%, var(--color-surface));
  }
  /* pinned: solid sun with dark text, so it reads the same in light and dark */
  .row.on, .row.on:has(> button:hover), button.row.on:hover, .fcell button.on, .fcell button.on:hover { background: var(--color-sun); }
  .row.on, .row.on :global(*), .fcell button.on, .fcell button.on * { color: var(--color-coal); }
  .row.on .badge { background: rgb(23 18 31 / .12); }
  .on kbd, .chip-kbd { background: #fff; color: var(--color-coal); border-color: var(--color-coal); box-shadow: 0 2px 0 var(--color-coal); }
  .on kbd.fnkey, .row.on kbd.fnkey :global(*) { color: #fff; }
  .row.on kbd.fnkey { background: var(--tab); color: #fff; }
  .chip-kbd { padding-block: 0; }
  .row button:focus-visible, .fcell button:focus-visible { outline: none; }
  .fcell button { transition: background-color .12s; }
  .fcell button:hover, .fcell button:focus-visible { background: color-mix(in oklab, var(--tab) 16%, var(--color-surface)); }
  kbd.fnkey { background: var(--tab); color: #fff; }
  .warn { color: color-mix(in oklab, var(--color-cherry) 80%, var(--color-ink)); font-weight: 700; }
  .warnbox { background: color-mix(in oklab, var(--color-cherry) 22%, var(--color-surface)); }
</style>
