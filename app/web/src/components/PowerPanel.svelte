<script>
  import { onMount } from "svelte";
  import { Moon, Zap, BatteryWarning, Infinity as Forever, Info, HeartPulse } from "@lucide/svelte";
  import { api } from "../lib/api.js";
  import { app, act, load } from "../lib/store.svelte.js";

  const sleep = $derived(app.state.lighting.sleep);
  const bat = $derived(app.state.battery);
  let busy = $state(false);

  const label = (s) => (s % 60 ? `${s / 60} min` : `${s / 60} min`);
  const OPTIONS = $derived([...app.catalog.sleepChoices.map((s) => ({ s, t: label(s) })), { s: 0, t: "Never" }]);
  const COLORS = ["#ffd23f", "#ffc83a", "#a8ec00", "#7fe36a", "#19d3c5", "#3b9dff", "#8b5cff", "#c06bff", "#ff3ea5", "#ff7a1a"];

  async function pick(s) {
    if (s === sleep || busy) return;
    busy = true;
    const prev = sleep;
    app.state.lighting.sleep = s;
    try { await act("sleep", { seconds: s }, s ? `Keyboard now sleeps after ${label(s)}` : "Keyboard will never sleep"); }
    catch { app.state.lighting.sleep = prev; load(); }
    finally { busy = false; }
  }

  let health = $state(null);
  async function loadHealth() { try { health = await api("battery-health"); } catch {} }
  onMount(() => { loadHealth(); const t = setInterval(loadHealth, 60000); return () => clearInterval(t); });
  const est = $derived(health?.estimate);
  const seen = $derived(est ? est.observedDischarge + est.observedCharge : 0);
  const verdict = $derived(!est?.health ? null : est.health >= 80 ? ["Good", "var(--color-lime)"] :
                           est.health >= 60 ? ["Worn", "var(--color-sun)"] : ["Replace soon", "var(--color-cherry)"]);

  const level = $derived(!bat ? "none" : bat.charging ? "charging" : bat.percent <= 15 ? "low" : bat.percent <= 40 ? "mid" : "ok");
  const FILL = { charging: "var(--color-aqua)", ok: "var(--color-lime)", mid: "var(--color-sun)", low: "var(--color-cherry)", none: "transparent" };
</script>

<div class="grid items-start gap-8 lg:grid-cols-[minmax(0,1.4fr)_minmax(300px,1fr)] xl:contents">
  <section class="area-list grid content-start gap-4">
    <div class="flex items-center gap-3">
      <span class="grid size-10 place-items-center rounded-xl border-[3px] border-ink bg-grape text-white shadow-pop-sm"><Moon size={20} strokeWidth={2.6} /></span>
      <div>
        <h2>Sleep after</h2>
        <p class="hint">How long the keyboard waits without a key press before it sleeps. Press any key to wake it.</p>
      </div>
    </div>

    <div class="stagger grid grid-cols-[repeat(auto-fill,minmax(120px,1fr))] gap-3" role="radiogroup" aria-label="Sleep after">
      {#each OPTIONS as o, i (o.s)}
        {@const on = sleep === o.s}
        <button role="radio" aria-checked={on} disabled={busy}
                class="grid justify-items-center gap-0.5 rounded-2xl border-[3px] border-ink px-3 py-3 font-black transition-all
                       {on ? 'text-coal shadow-pop -translate-x-0.5 -translate-y-0.5' : 'bg-surface shadow-pop-sm hover:-translate-y-0.5 hover:shadow-pop'}"
                style:background={on ? COLORS[i % COLORS.length] : null}
                onclick={() => pick(o.s)}>
          {#if o.s === 0}<Forever size={22} strokeWidth={2.8} />{:else}<span class="text-xl leading-none">{o.s / 60}</span>{/if}
          <span class="text-xs font-extrabold {on ? 'text-coal/70' : 'text-ink/55'}">{o.s === 0 ? "never sleep" : o.s === 60 ? "minute" : "minutes"}</span>
        </button>
      {/each}
    </div>

    {#if sleep === 0}
      <p class="m-0 flex items-start gap-2 rounded-xl border-2 border-ink bg-sun/30 px-3 py-2 text-sm font-semibold">
        <BatteryWarning size={18} strokeWidth={2.6} class="mt-px shrink-0" /> Never sleeping keeps the lights and radio on, so the battery runs down much faster.
      </p>
    {:else if sleep <= 90}
      <p class="hint flex items-center gap-1.5"><Info size={15} strokeWidth={2.6} /> Short times save the most battery, but the first key press after a pause only wakes the keyboard.</p>
    {/if}
  </section>

  <aside class="card area-aside grid gap-5" style:background="linear-gradient(160deg, var(--color-surface) 55%, var(--tab-tint))">
    <h2 class="text-2xl font-black">Battery</h2>
    {#if bat}
      <div class="flex items-center gap-5">
        <!-- big battery -->
        <div class="relative h-24 w-44 shrink-0 rounded-2xl border-[4px] border-ink bg-cream p-1.5 shadow-pop" aria-hidden="true">
          <div class="h-full rounded-[10px] transition-[width] duration-700" class:charge={bat.charging}
               style:width={Math.max(6, bat.percent) + "%"} style:background={FILL[level]}></div>
          <div class="absolute -right-[13px] top-1/2 h-9 w-2.5 -translate-y-1/2 rounded-r-md border-[3px] border-l-0 border-ink bg-cream"></div>
          {#if bat.charging}
            <Zap size={40} strokeWidth={2.4} fill="#ffd23f" class="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 text-coal drop-shadow-[2px_2px_0_#17121f]" />
          {/if}
        </div>
        <div class="grid">
          <span class="text-5xl font-black leading-none tabular-nums">{bat.percent}<span class="text-2xl">%</span></span>
          <span class="mt-1 font-extrabold" class:text-cherry={level === "low"}>
            {bat.charging ? "Charging" : level === "low" ? "Low, plug in soon" : bat.percent >= 100 ? "Full" : "On battery"}
          </span>
        </div>
      </div>
      <p class="hint text-xs">Updates while you type (checking an idle keyboard would keep it awake). When the cable is in and the battery is full, the keyboard stops charging, so it shows “Full”.</p>
    {:else}
      <p class="hint">The keyboard didn't report its battery. Press a key to wake it.</p>
    {/if}
    <div class="grid gap-3 border-t-[3px] border-dashed border-ink/20 pt-5">
      <h3 class="flex items-center gap-1.5"><HeartPulse size={14} strokeWidth={3} /> Battery health · estimate</h3>
      {#if est?.health != null}
        <div class="flex items-end gap-3">
          <span class="text-5xl font-black leading-none tabular-nums">~{est.health}<span class="text-2xl">%</span></span>
          <span class="sticker mb-1 text-coal" style:background={verdict[1]}>{verdict[0]}</span>
          <span class="sticker mb-1 bg-surface text-ink/60">{est.confidence} estimate</span>
        </div>
        <!-- likely range -->
        <div class="relative h-4 rounded-full border-[2.5px] border-ink bg-cream" aria-label={`Likely between ${est.low}% and ${est.high}%`}>
          <div class="absolute inset-y-0 rounded-full bg-lime/70" style:left={Math.min(est.low, 100) + "%"} style:width={Math.max(2, Math.min(est.high, 100) - est.low) + "%"}></div>
          <div class="absolute -inset-y-1 w-1 rounded-full bg-ink" style:left={`calc(${Math.min(est.health, 100)}% - 2px)`}></div>
        </div>
        <p class="hint text-xs">Likely between {est.low}% and {est.high}% of a new battery's capacity.</p>
      {:else}
        <p class="m-0 font-extrabold">Collecting data…</p>
        <div class="h-3.5 overflow-hidden rounded-full border-[2.5px] border-ink bg-cream">
          <div class="h-full bg-aqua transition-all duration-500" style:width={Math.min(100, (seen / (est?.needed ?? 10)) * 100) + "%"}></div>
        </div>
        <p class="hint text-xs">
          Just use the keyboard. While you type, a reading is taken every 10 minutes; the estimate appears once the
          battery has drained or charged about {est?.needed ?? 10}% ({seen}% so far, {est?.samples ?? 0} readings).
        </p>
      {/if}
      {#if health && !health.logging}
        <p class="m-0 rounded-xl border-2 border-ink bg-sun/30 px-3 py-2 text-xs font-semibold">
          The background logger isn't running, so no data is being collected. Turn it on by running
          <code class="font-mono">./install.sh</code> in the aula-f75 folder again.
        </p>
      {/if}
      <p class="m-0 text-xs text-ink/55">
        The F75 doesn't report wear, so this compares how fast yours drains (per hour awake, for your lighting) and charges
        against a new {health?.specs.capacity ?? 4000} mAh battery: about {health?.specs.hoursLit ?? 17.5} h with the lights on
        and {health?.specs.hoursDark ?? 266.5} h with them off. Sparse effects use less power than the model assumes, so they
        can make health read a little low.
      </p>
    </div>
  </aside>
</div>

<style>
  .charge { animation: charge 1.6s ease-in-out infinite; }
  @keyframes charge { 50% { opacity: .55; } }
</style>
