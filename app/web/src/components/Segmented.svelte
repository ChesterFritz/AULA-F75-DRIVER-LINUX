<script>
  let { options, value = $bindable(), label, onchange } = $props();
  function pick(v) { value = v; onchange?.(v); }
  function key(e, i) {
    if (!["ArrowRight", "ArrowLeft"].includes(e.key)) return;
    e.preventDefault();
    const n = options[(i + (e.key === "ArrowRight" ? 1 : options.length - 1)) % options.length];
    pick(n.value);
    e.currentTarget.parentElement.querySelectorAll("button")[options.indexOf(n)].focus();
  }
</script>

<div class="inline-flex flex-wrap gap-1 rounded-2xl border-[3px] border-ink bg-surface p-1 shadow-pop-sm" role="radiogroup" aria-label={label}>
  {#each options as o, i (o.value)}
    {@const on = value === o.value}
    <button type="button" role="radio" aria-checked={on} tabindex={on ? 0 : -1}
            class="inline-flex items-center gap-1.5 rounded-xl border-2 px-3.5 py-1.5 text-sm font-extrabold transition-all
                   {on ? 'border-ink text-white shadow-pop-sm' : 'border-transparent text-ink/60 hover:bg-ink/5 hover:text-ink'}"
            style:background={on ? "var(--tab)" : null}
            onclick={() => pick(o.value)} onkeydown={(e) => key(e, i)}>
      {#if o.icon}<o.icon size={16} strokeWidth={2.6} />{/if}{o.label}
    </button>
  {/each}
</div>
