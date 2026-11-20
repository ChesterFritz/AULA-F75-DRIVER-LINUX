<script>
  import { Power, Pipette } from "@lucide/svelte";
  import { app, setLighting, setPalette } from "../lib/store.svelte.js";
  import { MODE_LABEL, MODE_HINT } from "../lib/labels.js";
  import Slider from "./Slider.svelte";

  const RAINBOW = "conic-gradient(from 200deg, #ff5a5a, #ffd84d, #5dff7a, #4dd8ff, #6a5cff, #ff4dd8, #ff5a5a)";
  const SPEED = ["Slowest", "Slow", "Medium", "Fast", "Fastest"];
  // each effect card gets its own candy colour when picked
  const CANDY = ["#ff3ea5", "#ffd23f", "#a8ec00", "#19d3c5", "#3b6dff", "#8b5cff", "#ff7a1a"];

  const mode = $derived(app.state.lighting.mode);
  const info = $derived(app.catalog.modes.find((m) => m.id === mode));
  const ms = $derived(info ? app.state.lighting.modes[mode] : null);
  let lastMode = 1;
  $effect(() => { if (mode) lastMode = mode; });

  function chip(m) {
    const s = app.state.lighting.modes[m.id];
    if (!m.color || s.color === 7) return RAINBOW;
    return "#" + s.palette[s.color];
  }
  function toggle() { setLighting({ mode: mode ? 0 : lastMode }); }
</script>

<div class="grid items-start gap-8 lg:grid-cols-[minmax(0,1.6fr)_minmax(280px,1fr)] xl:contents">
  <section class="area-list">
    <div class="mb-4 flex items-center justify-between">
      <h2>Pick an effect</h2>
      <button class="sticker px-3.5 py-1.5 text-sm transition-colors {mode ? 'bg-lime' : 'bg-surface text-ink/60'}"
              role="switch" aria-checked={mode !== 0} onclick={toggle}>
        <Power size={16} strokeWidth={3} /> {mode ? "Lights on" : "Lights off"}
      </button>
    </div>
    <div class="stagger grid grid-cols-[repeat(auto-fill,minmax(186px,1fr))] gap-3 transition-opacity" class:opacity-50={!mode}>
      {#each app.catalog.modes as m, i (m.id)}
        {@const on = mode === m.id}
        {@const c = CANDY[i % CANDY.length]}
        <button
          class="group grid grid-cols-[auto_1fr] items-center gap-x-3 rounded-2xl border-[3px] border-ink px-3 py-2.5 text-left transition-all duration-100
                 {on ? 'text-coal shadow-pop -translate-x-0.5 -translate-y-0.5' : 'bg-surface shadow-pop-sm hover:-translate-y-0.5 hover:shadow-pop'}"
          style:background={on ? c : null}
          aria-pressed={on}
          onclick={() => setLighting({ mode: m.id })}
        >
          <span class="row-span-2 size-8 rounded-[10px] border-[2.5px] border-ink transition-transform group-hover:rotate-12"
                style:background={chip(m)}></span>
          <span class="text-sm font-extrabold">{MODE_LABEL[m.name] ?? m.name}</span>
          <span class="text-xs leading-tight {on ? 'text-coal/75' : 'text-ink/55'}">{MODE_HINT[m.name] ?? ""}</span>
        </button>
      {/each}
    </div>
  </section>

  <aside class="card area-aside sticky top-0 grid gap-6 xl:static" style:background="linear-gradient(160deg, var(--color-surface) 55%, var(--tab-tint))">
    {#if info && ms}
      <div class="flex items-center gap-3">
        <span class="size-10 rounded-xl border-[3px] border-ink shadow-pop-sm" style:background={chip(info)}></span>
        <h2 class="text-2xl font-black">{MODE_LABEL[info.name]}</h2>
      </div>
      <Slider label="Brightness" min={0} max={9} bind:value={ms.brightness} color="#ffd23f"
              valueText={ms.brightness === 0 ? "Off" : `${Math.round((ms.brightness / 9) * 100)}%`}
              onchange={(v) => setLighting({ mode, brightness: v })} />
      {#if info.speed}
        <Slider label="Speed" min={0} max={4} bind:value={ms.speed} valueText={SPEED[ms.speed]} color="#19d3c5"
                onchange={(v) => setLighting({ mode, speed: v })} />
      {/if}
      {#if info.color}
        <div class="grid gap-3">
          <h3>Colour</h3>
          <div class="flex flex-wrap gap-2" role="radiogroup" aria-label="Colour">
            {#each ms.palette as hex, i}
              <button class="size-9 rounded-xl border-[3px] border-ink shadow-pop-sm transition-transform hover:-translate-y-1 hover:rotate-6
                             aria-checked:scale-110 aria-checked:shadow-pop aria-checked:ring-4 aria-checked:ring-ink/15"
                      role="radio" aria-checked={ms.color === i} aria-label={`Colour ${i + 1}, #${hex}`}
                      style:background={"#" + hex} onclick={() => setLighting({ mode, color: i })}></button>
            {/each}
            <button class="size-9 rounded-xl border-[3px] border-ink shadow-pop-sm transition-transform hover:-translate-y-1 hover:rotate-6
                           aria-checked:scale-110 aria-checked:shadow-pop aria-checked:ring-4 aria-checked:ring-ink/15"
                    role="radio" aria-checked={ms.color === 7} aria-label="Rainbow"
                    style:background={RAINBOW} onclick={() => setLighting({ mode, color: 7 })}></button>
          </div>
          {#if ms.color !== 7}
            <label class="btn btn-sun relative justify-self-start overflow-hidden">
              <Pipette size={16} strokeWidth={2.6} /> Change this colour
              <input class="absolute inset-0 size-full cursor-pointer opacity-0" type="color" value={"#" + ms.palette[ms.color]}
                     onchange={(e) => setPalette(mode, ms.color, e.currentTarget.value.slice(1))}>
            </label>
          {/if}
        </div>
      {:else}
        <p class="hint">This effect uses its own rainbow colours. 🌈</p>
      {/if}
      <p class="m-0 text-xs text-ink/50">The preview on the keyboard is an approximation of the effect.</p>
    {:else}
      <h2 class="text-2xl font-black">Lights off</h2>
      <p class="hint">The backlight is off. Pick an effect or turn the lights back on.</p>
      <button class="btn btn-primary justify-self-start" onclick={toggle}><Power size={16} strokeWidth={3} /> Turn on</button>
    {/if}
  </aside>
</div>
