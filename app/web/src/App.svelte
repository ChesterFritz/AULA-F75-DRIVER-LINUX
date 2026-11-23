<script>
  import { onMount, untrack } from "svelte";
  import { Sun, Keyboard as KeyboardIcon, Workflow, Archive, Wifi, Usb, Loader, Check, CircleOff, Sparkles, Moon, Monitor, BatteryCharging, BookOpen, Mouse, Gauge, Activity, Bluetooth } from "@lucide/svelte";
  import { app, init, load } from "./lib/store.svelte.js";
  import { theme, setTheme } from "./lib/theme.svelte.js";
  import Keyboard from "./components/Keyboard.svelte";
  import LightingPanel from "./components/LightingPanel.svelte";
  import KeysPanel from "./components/KeysPanel.svelte";
  import MacrosPanel from "./components/MacrosPanel.svelte";
  import BackupsPanel from "./components/BackupsPanel.svelte";
  import PowerPanel from "./components/PowerPanel.svelte";
  import ManualPanel from "./components/ManualPanel.svelte";
  import MouseView from "./components/MouseView.svelte";
  import MousePanel from "./components/MousePanel.svelte";
  import { mouse, loadMouse, refreshMouseInfo } from "./lib/mouse.svelte.js";
  import Toasts from "./components/Toasts.svelte";
  import BatteryBadge from "./components/BatteryBadge.svelte";

  const TABS = [
    { id: "lighting", label: "Lighting", icon: Sun, color: "#ff3ea5", soft: "#ffd6ec", intro: "Pick an effect and tune it. The keyboard shows a live preview." },
    { id: "keys", label: "Keys", icon: KeyboardIcon, color: "#3b6dff", soft: "#d9e3ff", intro: "Click any key on the keyboard to change what it does." },
    { id: "macros", label: "Macros", icon: Workflow, color: "#8b5cff", soft: "#e6dcff", intro: "Sequences of key presses stored on the keyboard." },
    { id: "mouse", label: "Mouse", icon: Mouse, color: "#e8590c", soft: "#ffe0cc", intro: "Keychron mouse: click a button on the mouse, then pick what it should do." },
    { id: "power", label: "Power", icon: BatteryCharging, color: "#0fa968", soft: "#d3f5e4", intro: "Battery level and how soon the keyboard goes to sleep." },
    { id: "backups", label: "Backups", icon: Archive, color: "#ff7a1a", soft: "#ffe2cc", intro: "Save the whole setup, or go back to an earlier one." },
    { id: "manual", label: "Manual", icon: BookOpen, color: "#0c9bb8", soft: "#d0f3fa", intro: "Every shortcut and how-to from the quick start guide. Point at one to see its keys." },
  ];
  const current = $derived(TABS.find((t) => t.id === app.tab));
  const THEMES = [
    { id: "light", label: "Light", icon: Sun },
    { id: "dark", label: "Dark", icon: Moon },
    { id: "system", label: "Match system", icon: Monitor },
  ];

  $effect(() => {
    document.documentElement.style.setProperty("--tab", current.color);
  });
  // The Keychron mouse is read only when its tab is opened, so it never slows the keyboard down.
  // Only re-runs when the tab changes (loadMouse is untracked), so a failed read can't loop;
  // background retries are handled quietly inside loadMouse.
  $effect(() => {
    if (app.tab === "mouse") untrack(() => { if (!mouse.data) loadMouse(); });
  });
  $effect(() => {
    if (app.tab !== "mouse") return;
    const timer = setInterval(refreshMouseInfo, 15000);
    return () => clearInterval(timer);
  });

  function onRailKey(e, i) {
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    e.preventDefault();
    const next = TABS[(i + (e.key === "ArrowDown" ? 1 : TABS.length - 1)) % TABS.length];
    app.tab = next.id;
    document.getElementById("rail-" + next.id)?.focus();
  }

  onMount(init);
</script>

<!-- colourful drifting blobs behind everything -->
<div class="blobs pointer-events-none fixed inset-0 -z-10 overflow-hidden bg-dots" aria-hidden="true">
  <div class="blob -left-56 -top-56 size-[46rem] animate-float" style:--c="#ff3ea5"></div>
  <div class="blob -right-48 top-[10%] size-[42rem] animate-float [animation-delay:-5s]" style:--c="#19d3c5"></div>
  <div class="blob -bottom-72 left-[25%] size-[50rem] animate-float [animation-delay:-9s]" style:--c="#ffd23f"></div>
  <div class="blob -bottom-24 -left-40 size-[30rem] animate-float [animation-delay:-3s]" style:--c="#8b5cff"></div>
</div>

<div class="grid h-screen grid-cols-[112px_1fr] max-[720px]:grid-cols-1 max-[720px]:grid-rows-[1fr_auto]">
  <nav class="z-10 m-3 mr-0 flex flex-col items-center gap-6 rounded-3xl border-[3px] border-ink bg-surface py-4 shadow-pop-lg
              max-[720px]:order-2 max-[720px]:m-2 max-[720px]:flex-row max-[720px]:px-2 max-[720px]:py-2" aria-label="Sections">
    <div class="grid size-14 -rotate-6 place-items-center rounded-2xl border-[3px] border-ink bg-gradient-to-br from-pink via-sun to-aqua shadow-pop-sm
                transition-transform duration-300 hover:rotate-6 max-[720px]:hidden" aria-hidden="true">
      <span class="text-lg font-black tracking-tighter text-coal">F75</span>
    </div>
    <div class="grid w-full gap-2.5 px-2.5 max-[720px]:grid-flow-col" role="tablist" aria-orientation="vertical">
      {#each TABS as t, i (t.id)}
        {@const on = app.tab === t.id}
        <button
          id={"rail-" + t.id}
          role="tab"
          aria-selected={on}
          tabindex={on ? 0 : -1}
          class="rail-tab group grid justify-items-center gap-1 rounded-2xl border-[3px] px-1 pb-2 pt-2.5 text-[.74rem] font-extrabold transition-all
                 {on ? '-translate-x-0.5 -translate-y-0.5 border-ink text-white shadow-pop' : 'border-transparent text-ink/70 hover:border-ink hover:text-ink'}"
          style:background={on ? t.color : null}
          style:--soft={t.color}
          onclick={() => (app.tab = t.id)}
          onkeydown={(e) => onRailKey(e, i)}
        >
          <span class="group-hover:animate-wobble" style:color={on ? null : t.color}><t.icon size={22} strokeWidth={2.4} /></span>
          <span>{t.label}</span>
        </button>
      {/each}
    </div>
    <div class="mt-auto grid justify-items-center gap-1.5 max-[720px]:ml-auto max-[720px]:mt-0" role="radiogroup" aria-label="Theme">
      <span class="text-[.6rem] font-extrabold uppercase tracking-[.16em] text-ink/50 max-[720px]:hidden">Theme</span>
      <div class="flex gap-px rounded-lg border-2 border-ink bg-cream p-0.5">
        {#each THEMES as th (th.id)}
          {@const on = theme.choice === th.id}
          <button role="radio" aria-checked={on} aria-label={th.label} title={th.label}
                  class="grid size-6 place-items-center rounded-md transition-all
                         {on ? 'bg-sun text-coal shadow-pop-sm' : 'text-ink/55 hover:bg-ink/10 hover:text-ink'}"
                  onclick={(e) => setTheme(th.id, e)}>
            <th.icon size={14} strokeWidth={2.6} />
          </button>
        {/each}
      </div>
    </div>
  </nav>

  <main class:wide={app.tab === "mouse"} class="scroll-pop min-w-0 overflow-y-auto overflow-x-hidden px-[clamp(1.25rem,3vw,2.5rem)] pb-12 pt-5
               xl:grid xl:h-screen xl:overflow-hidden xl:px-7 xl:py-5 xl:gap-x-7
               xl:grid-cols-[minmax(0,1fr)_clamp(360px,27vw,470px)] xl:grid-rows-[auto_auto_minmax(0,1fr)]">
    <header class="top mx-auto mb-4 flex max-w-[1100px] items-start justify-between gap-4 max-[720px]:flex-col xl:mx-0 xl:max-w-none">
      <div class="flex items-center gap-4">
        {#key app.tab}
          <div class="grid size-14 shrink-0 rotate-[-4deg] place-items-center rounded-2xl border-[3px] border-ink text-white shadow-pop animate-pop-in"
               style:background={current.color}>
            <current.icon size={28} strokeWidth={2.4} />
          </div>
        {/key}
        <div>
          <h1 class="m-0 text-4xl font-black leading-none tracking-tight">
            {current.label}<span style:color={current.color}>.</span>
          </h1>
          <p class="hint mt-1.5">{current.intro}</p>
        </div>
      </div>
      <div class="flex flex-wrap justify-end gap-2" role="status">
        {#if app.save === "saving"}
          <span class="sticker bg-sun"><Loader size={14} strokeWidth={3} class="spin" /> Saving to {app.tab === "mouse" ? "mouse" : "keyboard"}</span>
        {:else if app.save === "saved"}
          <span class="sticker animate-pop-in bg-lime"><Check size={14} strokeWidth={3} /> Saved!</span>
        {/if}
        {#if app.tab === "mouse"}
          {@const mi = mouse.data?.info}
          {#if mi}
            <button type="button" class="sticker bg-surface text-ink hover:-translate-y-0.5" title="Change DPI (step {mi.dpi.current + 1} of {mi.dpi.steps.length})"
                    onclick={() => (mouse.section = "dpi")}>
              <Gauge size={14} strokeWidth={3} /> <span class="tabular-nums">{mi.dpi.steps[mi.dpi.current]}</span> DPI
            </button>
            {#if mi.polling.steps[mi.polling.current]}
              <button type="button" class="sticker bg-surface text-ink hover:-translate-y-0.5" title="Change polling rate"
                      onclick={() => (mouse.section = "poll")}>
                <Activity size={14} strokeWidth={3} /> <span class="tabular-nums">{mi.polling.steps[mi.polling.current]}</span> Hz
              </button>
            {/if}
            <BatteryBadge battery={mi.battery} device={mouse.data.name} />
            <span class="sticker bg-aqua">
              {#if mi.mode === "Bluetooth"}<Bluetooth size={14} strokeWidth={3} /> Bluetooth{:else if mi.mode === "USB cable"}<Usb size={14} strokeWidth={3} /> USB cable{:else}<Wifi size={14} strokeWidth={3} /> 2.4G receiver{/if}
            </span>
          {:else if !mouse.data && !mouse.loading}
            <span class="sticker bg-cherry text-white"><CircleOff size={14} strokeWidth={3} /> Not connected</span>
          {/if}
        {:else if app.state?.battery}
          <BatteryBadge battery={app.state.battery} />
        {/if}
        {#if app.tab === "mouse"}
        {:else if app.state}
          <span class="sticker bg-aqua">
            {#if app.state.kind === "2.4G dongle"}<Wifi size={14} strokeWidth={3} /> 2.4G receiver{:else}<Usb size={14} strokeWidth={3} /> USB cable{/if}
          </span>
        {:else if !app.loading}
          <span class="sticker bg-cherry text-white"><CircleOff size={14} strokeWidth={3} /> Not connected</span>
        {/if}
      </div>
    </header>

    <section class="stage relative mx-auto mb-6 max-w-[1100px] rounded-[2rem] border-[3px] border-ink p-[5px] shadow-pop-lg
                    xl:mx-0 xl:mb-5 xl:w-full xl:max-w-none"
             class:compact={app.tab === "macros" || app.tab === "backups" || app.tab === "power" || app.tab === "manual"}
             aria-label={app.tab === "mouse" ? "Mouse" : "Keyboard"}>
      <div class="relative overflow-hidden stage-mat rounded-[1.6rem] border-[3px] border-ink px-[clamp(1rem,4vw,3rem)] py-[clamp(1rem,3vw,2rem)] xl:px-8 xl:py-5">
        <div class="stage-glow pointer-events-none absolute inset-0 transition-[background] duration-500"
             style="background: radial-gradient(60% 85% at 50% 115%, var(--tab), transparent 70%)"></div>
        {#if app.tab !== "mouse"}
          <span class="sticker absolute left-4 top-3 z-10 rotate-[-4deg] bg-sun text-[.65rem] tracking-wider max-[720px]:hidden">
            <Sparkles size={12} strokeWidth={3} /> LIVE PREVIEW
          </span>
        {/if}
        {#if app.tab === "mouse"}<MouseView />{:else}<Keyboard />{/if}
        {#if app.tab === "mouse" && !mouse.data}
          <div class="absolute inset-0 z-20 grid place-content-center justify-items-center gap-3 bg-[#1a1524]/80 p-4 text-center text-white backdrop-blur-sm">
            {#if mouse.loading}
              <Loader size={34} class="spin text-sun" />
              <p class="m-0 text-xl font-black">Reading the mouse…</p>
            {:else}
              <p class="m-0 text-2xl font-black">{mouse.error?.includes("wake") ? "Mouse is asleep" : "Mouse not found"}</p>
              <p class="hint text-white/75">{mouse.error || "Plug in the Keychron receiver, switch the mouse on and move it to wake it."}</p>
              <button class="btn btn-sun" onclick={() => loadMouse()}>Try again</button>
              <p class="m-0 text-xs text-white/55">Checking again every few seconds…</p>
            {/if}
          </div>
        {/if}
        {#if !app.state && app.tab !== "mouse" && !(app.tab === "manual" && app.layout)}
          <div class="absolute inset-0 z-20 grid place-content-center justify-items-center gap-3 bg-[#1a1524]/80 p-4 text-center text-white backdrop-blur-sm">
            {#if app.loading}
              <Loader size={34} class="spin text-sun" />
              <p class="m-0 text-xl font-black">Reading the keyboard…</p>
            {:else}
              <p class="m-0 text-2xl font-black">Keyboard not found</p>
              <p class="hint text-white/75">{app.error || "Plug in the 2.4G receiver or the USB cable, then press a key to wake the keyboard."}</p>
              <button class="btn btn-sun" onclick={load}>Try again</button>
            {/if}
          </div>
        {/if}
      </div>
    </section>

    <div class="mx-auto max-w-[1100px] xl:contents" role="tabpanel" aria-labelledby={"rail-" + app.tab}>
      {#if app.tab === "manual"}<ManualPanel />
      {:else if app.tab === "mouse"}<MousePanel />
      {:else if app.state && app.catalog}
        {#if app.tab === "lighting"}<LightingPanel />
        {:else if app.tab === "keys"}<KeysPanel />
        {:else if app.tab === "macros"}<MacrosPanel />
        {:else if app.tab === "power"}<PowerPanel />
        {:else}<BackupsPanel />{/if}
      {/if}
    </div>
  </main>
</div>
<Toasts />

<style>
  .rail-tab[aria-selected="false"]:hover { background: color-mix(in oklab, var(--soft) 22%, var(--color-surface)); }
  /* soft gradient blobs: no blur filter, so they're cheap to animate */
  .blob {
    position: absolute; border-radius: 50%; will-change: translate, scale;
    background: radial-gradient(closest-side, color-mix(in srgb, var(--c) 42%, transparent), transparent);
  }
  :global([data-theme="dark"]) .blobs { opacity: .65; }
  /* the "desk mat" behind the keyboard follows the theme */
  .stage-mat {
    background-color: var(--mat);
    background-image: radial-gradient(color-mix(in oklab, var(--mat-dot) 18%, transparent) 1.3px, transparent 1.3px);
    background-size: 16px 16px;
  }
  .stage-glow { opacity: var(--mat-glow); }
  .stage {
    background: linear-gradient(110deg, #ff3ea5, #ffd23f, #a8ec00, #19d3c5, #3b6dff, #8b5cff, #ff3ea5);
    background-size: 300% 100%;
    animation: hue 14s linear infinite;
  }
  @keyframes hue { to { background-position: 300% 0; } }
  .stage :global(.board) { transition: width .35s cubic-bezier(.2, .7, .2, 1); width: min(100%, 820px); }
  .stage.compact :global(.board) { width: min(100%, 520px); }

  /* PC screens: keyboard + lists on the left, settings column on the right, no page scroll */
  @media (min-width: 1200px) {
    main { grid-template-areas: "top top" "stage aside" "list aside"; }
    .top { grid-area: top; }
    .stage { grid-area: stage; }
    .stage :global(.board) { width: min(100%, 1100px, calc((100vh - 490px) * 2.39)); }
    .stage.compact :global(.board) { width: min(100%, 640px, calc((100vh - 490px) * 2.39)); }
    main :global(.area-list) { grid-area: list; min-height: 0; overflow-y: auto; padding: 4px 1rem 1.4rem 4px; align-content: start; }
    main :global(.area-aside) { grid-area: aside; align-self: start; max-height: calc(100% - 8px); overflow-y: auto; }
    /* Mouse tab: launcher-style, the picker spans the full width under the mouse */
    main.wide { grid-template-areas: "top top" "stage stage" "list list"; }
    main.wide :global(.area-list) { padding: 1rem; margin: 4px 4px 1.2rem; }
  }
</style>
