<script>
  import { Zap } from "@lucide/svelte";
  let { battery } = $props();

  const pct = $derived(battery.percent);
  const level = $derived(battery.charging ? "charging" : pct <= 15 ? "low" : pct <= 40 ? "mid" : "ok");
  const FILL = { charging: "var(--color-aqua)", ok: "var(--color-lime)", mid: "var(--color-sun)", low: "var(--color-cherry)" };
  const title = $derived(
    battery.charging ? `Keyboard battery ${pct}%, charging` :
    pct <= 15 ? `Keyboard battery ${pct}%, low: plug in the cable` : `Keyboard battery ${pct}%`);
</script>

<span class="sticker gap-2 bg-surface text-ink" class:low={level === "low"} {title} aria-label={title}>
  <!-- battery body with a fill bar -->
  <span class="relative inline-flex h-3.5 w-7 items-center rounded-[4px] border-2 border-ink p-px" aria-hidden="true">
    <span class="h-full rounded-[2px] transition-[width] duration-700" class:pulse={battery.charging}
          style:width={Math.max(8, pct) + "%"} style:background={FILL[level]}></span>
    <span class="absolute -right-[4px] top-1/2 h-1.5 w-[3px] -translate-y-1/2 rounded-r-sm bg-ink"></span>
    {#if battery.charging}
      <Zap size={11} strokeWidth={3} fill="currentColor" class="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 text-coal" />
    {/if}
  </span>
  <span class="tabular-nums">{pct}%</span>
  {#if battery.charging}<span class="font-bold text-ink/60">Charging</span>{/if}
</span>

<style>
  .pulse { animation: charge 1.6s ease-in-out infinite; }
  @keyframes charge { 50% { opacity: .55; } }
  .low { animation: nudge 2.4s ease-in-out infinite; border-color: var(--color-cherry); }
  @keyframes nudge { 0%, 90%, 100% { rotate: 0deg; } 93% { rotate: -4deg; } 97% { rotate: 4deg; } }
</style>
