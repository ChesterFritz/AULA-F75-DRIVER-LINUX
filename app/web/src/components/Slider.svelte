<script>
  let { value = $bindable(), min = 0, max = 10, label, valueText, onchange, low, high, color = "var(--tab)" } = $props();
  const p = $derived(((value - min) / (max - min)) * 100);
</script>

<div class="grid gap-2.5">
  <div class="flex items-center justify-between">
    <h3>{label}</h3>
    <output class="rounded-lg border-2 border-ink bg-surface px-2 py-0.5 text-sm font-black tabular-nums shadow-pop-sm">{valueText ?? value}</output>
  </div>
  <input type="range" {min} {max} step="1" bind:value aria-label={label} aria-valuetext={valueText}
         style:--p={p + "%"} style:--c={color} oninput={() => onchange?.(+value)}>
  {#if low || high}
    <div class="flex justify-between text-xs text-ink/50" aria-hidden="true"><span>{low}</span><span>{high}</span></div>
  {/if}
</div>

<style>
  input {
    appearance: none; width: 100%; height: 16px; border-radius: 99px; margin: 0;
    border: 3px solid var(--color-ink); box-sizing: content-box;
    background: linear-gradient(to right, var(--c) var(--p), var(--color-surface) var(--p));
  }
  input::-webkit-slider-thumb {
    appearance: none; width: 28px; height: 28px; border-radius: 10px; background: var(--color-surface);
    border: 3px solid var(--color-ink); box-shadow: 2px 2px 0 var(--color-shadow); cursor: grab;
    transition: transform .12s cubic-bezier(.2, 1.6, .4, 1);
  }
  input:hover::-webkit-slider-thumb { transform: rotate(8deg); }
  input:active::-webkit-slider-thumb { transform: scale(1.15) rotate(-8deg); cursor: grabbing; }
</style>
