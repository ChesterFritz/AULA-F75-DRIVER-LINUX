<script>
  // Keychron mouse, laid out like Keychron Launcher's "Customize" page: one photo at a time
  // (top / side) with a callout for every button showing what it does now.
  // Click a callout or dot to select that button; click it again (or empty space, or Esc) to deselect.
  import { RotateCcw } from "@lucide/svelte";
  import { mouse, describeMouse, mouseImage, selectMouseButton, resetAllMouse } from "../lib/mouse.svelte.js";

  // Coordinate box (viewBox units): callout column | photo (square) | callout column.
  const W = 300, PHOTO_X = 100, PHOTO = 100, LEFT_EDGE = 92, RIGHT_EDGE = 208;
  const ZOOM = 1.15;               // Keychron's renders have wide empty margins
  let figH = $state(300);          // measured figure height (px)
  const GAP = $derived(Math.max(12, (52 / Math.max(figH, 1)) * 100)); // callouts are ~48px tall

  const byId = $derived(Object.fromEntries((mouse.data?.buttons ?? []).map((b) => [b.id, b])));
  const art = $derived(mouse.data?.art ?? null);
  const views = $derived(art ? Array.from({ length: art.images }, (_, n) => n) : []);
  const VIEW_NAMES = ["Top", "Side"];

  const z = (p) => 50 + (p - 50) * ZOOM;
  const side = (s) => (s.dir === "left" || s.dir === "up" ? "left" : "right");

  // Spread the callouts on one side so they never overlap, keeping each near its dot.
  function spread(list) {
    list.sort((a, b) => a.dy - b.dy);
    const lo = GAP / 2, hi = 100 - GAP / 2;
    list.forEach((c, i) => (c.cy = Math.max(c.dy, i ? list[i - 1].cy + GAP : lo)));
    for (let i = list.length - 1; i >= 0; i--) {
      const limit = i === list.length - 1 ? hi : list[i + 1].cy - GAP;
      if (list[i].cy > limit) list[i].cy = limit;
    }
    return list;
  }

  const spots = $derived.by(() => {
    if (!art) return [];
    const all = Object.entries(art.spots)
      .filter(([id, s]) => s.image === mouse.view && byId[id])
      .map(([id, s]) => ({ id, side: side(s), dx: PHOTO_X + z(s.x) * PHOTO / 100, dy: z(s.y) }));
    return [...spread(all.filter((c) => c.side === "left")), ...spread(all.filter((c) => c.side === "right"))];
  });

  const changed = (id) => byId[id] && byId[id].action !== "default";
  const pct = (u) => `${(u / W) * 100}%`;
  let hover = $state(null);

  function onKey(e) {
    if (e.key === "Escape" && mouse.selected && !e.target.closest?.("input")) selectMouseButton(null);
  }
  // Clicking empty space on the stage (not a callout, dot or control) deselects.
  function onStageClick(e) {
    if (!e.target.closest("button")) selectMouseButton(null);
  }
</script>

<svelte:window onkeydown={onKey} />

{#if mouse.data}
  <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
  <div class="relative z-10 text-ink" onclick={onStageClick}>
    {#if art}
      <div class="figure relative mx-auto" bind:clientHeight={figH}>
        <!-- photo -->
        <div class="pointer-events-none absolute inset-y-0" style:left={pct(PHOTO_X)} style:width={pct(PHOTO)}>
          {#key mouse.view}
            <img src={mouseImage(mouse.view)} alt="{mouse.data.name}, {VIEW_NAMES[mouse.view] ?? 'view'}" draggable="false"
                 class="photo size-full select-none object-contain drop-shadow-[0_18px_24px_rgba(0,0,0,.35)]" style:scale={ZOOM} />
          {/key}
        </div>

        <!-- leader lines -->
        <svg class="pointer-events-none absolute inset-0 size-full" viewBox="0 0 {W} 100" preserveAspectRatio="none" aria-hidden="true">
          {#each spots as c (c.id)}
            {@const on = mouse.selected === c.id}
            {@const x0 = c.side === "left" ? LEFT_EDGE : RIGHT_EDGE}
            {@const x1 = c.side === "left" ? PHOTO_X + 6 : PHOTO_X + PHOTO - 6}
            <polyline points="{x0},{c.cy} {x1},{c.cy} {c.dx},{c.dy}" fill="none" vector-effect="non-scaling-stroke"
                      class="lead {on ? 'lead-on' : hover === c.id ? 'lead-hot' : changed(c.id) ? 'lead-changed' : ''}" />
          {/each}
        </svg>

        <!-- dots on the photo -->
        {#each spots as c (c.id)}
          {@const on = mouse.selected === c.id}
          <button type="button" class="spot absolute z-10 -translate-x-1/2 -translate-y-1/2" style:left={pct(c.dx)} style:top="{c.dy}%"
                  aria-label={byId[c.id].label} aria-pressed={on} tabindex="-1"
                  onclick={() => selectMouseButton(c.id)} onmouseenter={() => (hover = c.id)} onmouseleave={() => (hover = null)}>
            <span class="dot {on ? 'dot-on' : changed(c.id) ? 'dot-changed' : ''} {hover === c.id && !on ? 'scale-125' : ''}"></span>
          </button>
        {/each}

        <!-- callouts: button name + what it does now -->
        {#each spots as c (c.id)}
          {@const b = byId[c.id]}
          {@const on = mouse.selected === c.id}
          <button type="button" aria-pressed={on}
                  class="callout absolute z-20 {c.side === 'left' ? 'text-right' : 'text-left'} {on ? 'callout-on' : changed(c.id) ? 'callout-changed' : ''} {hover === c.id ? 'callout-hot' : ''}"
                  style:right={c.side === "left" ? pct(W - LEFT_EDGE) : null}
                  style:left={c.side === "right" ? pct(RIGHT_EDGE) : null}
                  style:top="{c.cy}%"
                  title={on ? "Selected: click again to deselect" : `Click to change ${b.label}`}
                  onclick={() => selectMouseButton(c.id)} onmouseenter={() => (hover = c.id)} onmouseleave={() => (hover = null)}>
            <span class="block truncate text-[.66rem] font-extrabold uppercase tracking-wider opacity-60">{b.label}</span>
            <span class="block truncate text-sm font-black">{describeMouse(b.action)}</span>
          </button>
        {/each}
      </div>

      <!-- view switch (the launcher's pager) + reset -->
      <div class="relative mt-3 flex items-center justify-center">
        <div class="inline-flex gap-1 rounded-full border-[3px] border-ink bg-surface p-1 shadow-pop-sm" role="radiogroup" aria-label="View">
          {#each views as n}
            {@const count = Object.entries(art.spots).filter(([id, s]) => s.image === n && byId[id]).length}
            <button type="button" role="radio" aria-checked={mouse.view === n}
                    class="rounded-full px-4 py-1 text-xs font-extrabold transition-all {mouse.view === n ? 'text-white' : 'text-ink/60 hover:text-ink'}"
                    style:background={mouse.view === n ? "var(--tab)" : null}
                    onclick={() => (mouse.view = n)}>{VIEW_NAMES[n] ?? `View ${n + 1}`} · {count}</button>
          {/each}
        </div>
        <button type="button" class="btn btn-line absolute right-0 !min-h-0 !px-3 !py-1.5 text-xs"
                disabled={!mouse.data.buttons.some((b) => b.action !== "default")}
                onclick={resetAllMouse}><RotateCcw size={14} strokeWidth={3} /> Reset all</button>
      </div>
    {:else}
      <p class="hint py-16 text-center">Couldn't download Keychron's pictures of this mouse. Pick a button from the list below instead.</p>
    {/if}
  </div>
{:else}
  <!-- empty stage; App.svelte shows the "Reading / not found" overlay on top -->
  <div class="min-h-[300px]"></div>
{/if}

<style>
  /* keep the 300:100 box exact, so the dots stay on the photo */
  .figure { aspect-ratio: 300 / 100; width: min(100%, 1150px, calc(max(240px, 100vh - 580px) * 3)); }
  .photo { animation: fade .25s ease-out; }
  @keyframes fade { from { opacity: 0; translate: 0 6px; } }
  .lead { stroke: color-mix(in oklab, var(--color-ink) 35%, transparent); stroke-width: 1.5; transition: stroke .15s; }
  .lead-changed { stroke: #5b8cff; }
  .lead-hot { stroke: var(--color-ink); stroke-width: 2; }
  .lead-on { stroke: var(--color-sun); stroke-width: 3; }
  .spot { display: grid; place-items: center; width: 24px; height: 24px; border-radius: 999px; cursor: pointer; }
  .dot {
    width: 11px; height: 11px; border-radius: 999px; background: #fff; border: 2px solid #17121f;
    box-shadow: 0 0 0 4px rgba(255, 255, 255, .28); transition: transform .15s, background .15s;
  }
  .dot-changed { background: #5b8cff; box-shadow: 0 0 0 4px rgba(91, 140, 255, .35); }
  .dot-on { background: var(--color-sun); box-shadow: 0 0 0 5px rgba(255, 210, 63, .5); transform: scale(1.3); }
  .callout {
    transform: translateY(-50%); width: min(29%, 250px); padding: .3rem .7rem; border-radius: .9rem;
    border: 2px solid var(--color-ink); background: var(--color-surface); color: var(--color-ink);
    box-shadow: 2px 2px 0 var(--color-ink); cursor: pointer; transition: transform .12s, box-shadow .12s, background .12s;
  }
  .callout:focus-visible { outline: 3px solid var(--tab); outline-offset: 2px; }
  .callout-hot { transform: translateY(calc(-50% - 2px)); box-shadow: 3px 4px 0 var(--color-ink); }
  .callout-changed { border-color: #5b8cff; box-shadow: 2px 2px 0 #5b8cff; }
  .callout-on { background: var(--color-sun); color: var(--color-coal); border-color: var(--color-ink); box-shadow: 3px 3px 0 var(--color-ink); }
</style>
