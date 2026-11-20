<script>
  import { onMount } from "svelte";
  import { Save, History, FileClock } from "@lucide/svelte";
  import { app, act, load } from "../lib/store.svelte.js";
  import { api } from "../lib/api.js";

  let list = $state([]);
  let busy = $state("");

  async function refresh() { try { list = await api("backups"); } catch { list = []; } }
  onMount(refresh);

  function title(f) {
    const m = f.file.match(/^backup-(\d{4})-(\d\d)-(\d\d)-(\d\d)(\d\d)\d\d\.json$/);
    if (f.dir !== "backups" || !m) return f.label;
    const d = new Date(+m[1], +m[2] - 1, +m[3], +m[4], +m[5]);
    return d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
  }
  const what = (f) => (f.file.endsWith(".af75") ? "Lighting only" : "Lighting, colours, keys and macros");

  async function backup() {
    busy = "save";
    try { await act("backup", {}, "Backup saved"); await refresh(); } catch {} finally { busy = ""; }
  }
  async function restore(f) {
    if (!confirm(`Restore “${title(f)}”? This replaces the current ${f.file.endsWith(".af75") ? "lighting" : "lighting, keys and macros"}.`)) return;
    busy = f.file;
    try { await act("restore", { file: f.file, dir: f.dir }, "Backup restored"); await load(); } catch {} finally { busy = ""; }
  }
</script>

<div class="grid items-start gap-8 lg:grid-cols-[minmax(260px,.8fr)_minmax(0,1.4fr)] xl:contents">
  <section class="card area-aside grid justify-items-start gap-4" style:background="linear-gradient(160deg, var(--color-surface) 50%, var(--tab-tint))">
    <div class="grid size-14 -rotate-6 place-items-center rounded-2xl border-[3px] border-ink text-white shadow-pop" style:background="var(--tab)">
      <Save size={28} strokeWidth={2.4} />
    </div>
    <h2 class="text-2xl font-black">Save what's on the keyboard</h2>
    <p class="hint">Stores lighting, colours, both key layers and all macros in a file you can restore later.</p>
    <button class="btn btn-primary" disabled={!!busy} onclick={backup}>Save a backup now</button>
  </section>

  <section class="area-list">
    <h2 class="mb-4">Saved backups</h2>
    {#if list.length}
      <ul class="stagger m-0 grid list-none gap-3 p-0 xl:grid-cols-[repeat(auto-fill,minmax(420px,1fr))]">
        {#each list as f, i (f.dir + f.file)}
          <li class="flex items-center gap-3.5 rounded-2xl border-[3px] border-ink bg-surface py-2.5 pl-3 pr-2.5 shadow-pop-sm transition-all hover:-translate-y-0.5 hover:shadow-pop">
            <span class="grid size-10 shrink-0 place-items-center rounded-xl border-[2.5px] border-ink text-coal"
                  style:background={["#19d3c5", "#ffd23f", "#ff3ea5", "#a8ec00", "#8b5cff"][i % 5]}>
              <FileClock size={20} strokeWidth={2.4} />
            </span>
            <div class="grid min-w-0 flex-1"><strong class="font-extrabold">{title(f)}</strong><small class="text-ink/55">{what(f)}</small></div>
            <button class="btn btn-line px-3" disabled={!!busy} onclick={() => restore(f)}>
              <History size={16} strokeWidth={2.8} /> {busy === f.file ? "Restoring…" : "Restore"}
            </button>
          </li>
        {/each}
      </ul>
    {:else}
      <p class="hint rounded-2xl border-[3px] border-dashed border-ink/30 bg-surface/60 px-4 py-3">No backups yet.</p>
    {/if}
  </section>
</div>
