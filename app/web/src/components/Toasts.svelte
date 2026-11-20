<script>
  import { CircleCheck, TriangleAlert } from "@lucide/svelte";
  import { toasts } from "../lib/store.svelte.js";
</script>

<div class="fixed bottom-5 right-5 z-50 grid max-w-[min(420px,90vw)] gap-2.5" aria-live="polite">
  {#each toasts as t (t.id)}
    <div class="flex animate-pop-in items-start gap-2.5 rounded-2xl border-[3px] border-ink px-4 py-3 text-sm font-extrabold shadow-pop
                {t.kind === 'err' ? 'bg-cherry text-white' : 'bg-lime text-coal'}"
         role={t.kind === "err" ? "alert" : "status"}>
      {#if t.kind === "err"}<TriangleAlert size={18} strokeWidth={2.8} class="mt-px shrink-0" />{:else}<CircleCheck size={18} strokeWidth={2.8} class="mt-px shrink-0" />{/if}
      <span>{t.msg}</span>
    </div>
  {/each}
</div>
