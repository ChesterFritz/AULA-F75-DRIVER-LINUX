<script>
  import { app } from "../lib/store.svelte.js";
  import { keyLabel, describe, codeToName } from "../lib/labels.js";
  import { createSim, hexToRgb } from "../lib/effects.js";

  let board = $state();
  let under = $state();   // light spilling between the caps
  let tint = $state();    // light shining through the caps
  let glow = $state();    // ambient light on the desk
  let hover = $state(null);
  let pointer = null;

  const L = $derived(app.layout);
  const editing = $derived(app.tab === "keys" && !!app.state);
  const keys = $derived(app.state ? app.state.layers[app.layer] : {});

  function lightSettings() {
    const s = app.state;
    if (!s || !app.catalog) return null;
    if (app.preview) return { name: app.preview, base: null, speed: 2, bright: 1 };
    const m = s.lighting.mode;
    const info = app.catalog.modes.find((x) => x.id === m);
    if (!info) return null;
    const ms = s.lighting.modes[m];
    const base = info.color && ms.color !== 7 ? hexToRgb(ms.palette[ms.color]) : null;
    return { name: info.name, base, speed: ms.speed, bright: 0.3 + (ms.brightness / 9) * 0.7 };
  }

  function fit(c, cw, ch, dpr) {
    const w = Math.round(cw * dpr), h = Math.round(ch * dpr);
    if (c.width !== w || c.height !== h) { c.width = w; c.height = h; }
  }

  $effect(() => {
    if (!under || !L) return;
    const sim = createSim(L.keys, L.width, L.height);
    const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
    const uctx = under.getContext("2d"), tctx = tint.getContext("2d"), gctx = glow.getContext("2d");
    let raf, last = performance.now();
    const onKey = (e) => { const n = codeToName(e.code); if (n) sim.poke(n); };
    window.addEventListener("keydown", onKey);

    const loop = (now) => {
      raf = requestAnimationFrame(loop);
      if (document.hidden) return;
      const dt = Math.min(0.1, (now - last) / 1000);
      last = now;
      const dpr = devicePixelRatio || 1;
      const cw = board.clientWidth, ch = board.clientHeight;
      fit(under, cw, ch, dpr); fit(tint, cw, ch, dpr);
      for (const c of [uctx, tctx]) { c.setTransform(1, 0, 0, 1, 0, 0); c.clearRect(0, 0, under.width, under.height); }
      gctx.clearRect(0, 0, glow.width, glow.height);
      const ls = lightSettings();
      if (!ls) return;
      const sx = (dpr * cw) / L.width, sy = (dpr * ch) / L.height;
      uctx.setTransform(sx, 0, 0, sy, 0, 0);
      tctx.setTransform(sx, 0, 0, sy, 0, 0);
      uctx.globalCompositeOperation = "lighter";
      const cols = sim.frame(ls.name, ls.base, ls.speed, reduce ? 3 : now / 1000, reduce ? 0 : dt, pointer);
      sim.keys.forEach((k, i) => {
        const [r, g, b, a] = cols[i];
        if (a < 0.02) return;
        const alpha = a * ls.bright;
        const rgba = (x) => `rgba(${r},${g},${b},${(alpha * x).toFixed(3)})`;
        // elliptical spill shaped like the key, so wide keys don't bloom
        const rad = k.h * 0.8, stretch = k.w / k.h;
        uctx.save();
        uctx.translate(k.x + k.w / 2, k.y + k.h / 2);
        uctx.scale(stretch, 1);
        const grd = uctx.createRadialGradient(0, 0, 0, 0, 0, rad);
        grd.addColorStop(0, rgba(1)); grd.addColorStop(0.6, rgba(0.7)); grd.addColorStop(1, rgba(0));
        uctx.fillStyle = grd;
        uctx.fillRect(-rad, -rad, rad * 2, rad * 2);
        uctx.restore();
        if (k.accent) return;   // coloured accent caps stay clean
        tctx.fillStyle = rgba(0.9);
        tctx.beginPath();
        tctx.roundRect(k.x, k.y, k.w, k.h, 7);
        tctx.fill();
      });
      gctx.globalAlpha = ls.bright;
      gctx.drawImage(under, 0, 0, glow.width, glow.height);
    };
    raf = requestAnimationFrame(loop);
    return () => { cancelAnimationFrame(raf); window.removeEventListener("keydown", onKey); };
  });

  function move(e) {
    const r = board.getBoundingClientRect();
    pointer = { x: (e.clientX - r.left) / r.width, y: (e.clientY - r.top) / r.height };
  }
  const pct = (v, total) => (v / total) * 100 + "%";
</script>

<div class="wrap" class:editing>
  <canvas class="glow" bind:this={glow} width="96" height="40" aria-hidden="true"></canvas>
  {#if L}
  <!-- svelte-ignore a11y_no_static_element_interactions (pointer only feeds the preview) -->
  <div class="board" class:debug={app.debug} bind:this={board} onpointermove={move} onpointerleave={() => (pointer = null)}
       style:aspect-ratio={`${L.width} / ${L.height}`}>
    <svg class="layer" viewBox={`0 0 ${L.width} ${L.height}`} role="img" aria-label="AULA F75 keyboard">
      <defs>
        <linearGradient id="case" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="#fdfbff" /><stop offset="1" stop-color="#d9d3e6" />
        </linearGradient>
      </defs>
      <rect x="1" y="1" width={L.width - 2} height={L.height - 2} rx="22" fill="url(#case)" stroke="#17121f" stroke-width="4" />
      <rect x={L.pad - 6} y={L.pad - 6} width={L.width - 2 * L.pad + 12} height={L.height - 2 * L.pad + 12} rx="10"
            fill="#120e1a" stroke="#17121f" stroke-width="2" />
    </svg>
    <canvas class="layer under" bind:this={under}></canvas>
    <svg class="layer" viewBox={`0 0 ${L.width} ${L.height}`} aria-hidden="true">
      <defs>
        <linearGradient id="capTop" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="#ffffff" /><stop offset="1" stop-color="#ece6f6" />
        </linearGradient>
        <linearGradient id="capTopAcc" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" style="stop-color: var(--tab)" /><stop offset="1" style="stop-color: color-mix(in oklab, var(--tab), #17121f 18%)" />
        </linearGradient>
        <radialGradient id="knob" cx=".4" cy=".35" r=".7">
          <stop offset="0" stop-color="#ffe680" /><stop offset=".6" stop-color="#ffd23f" /><stop offset="1" stop-color="#e0a800" />
        </radialGradient>
      </defs>
      {#each L.keys as k (k.key)}
        <g class="cap" class:accent={k.accent}>
          <rect class="skirt" x={k.x} y={k.y} width={k.w} height={k.h} rx="7" />
          <rect x={k.x + 5} y={k.y + 3} width={k.w - 10} height={k.h - 11} rx="5"
                fill={k.accent ? "url(#capTopAcc)" : "url(#capTop)"} />
          {#if k.shift}
            <text x={k.x + 10} y={k.y + 19} class="legend sm">{k.shift}</text>
            <text x={k.x + 10} y={k.y + 37} class="legend">{k.main}</text>
          {:else if k.main.length > 1 && k.w > 60}
            <text x={k.x + 10} y={k.y + 24} class="legend sm">{k.main}</text>
          {:else}
            <text x={k.x + k.w / 2} y={k.y + k.h / 2 - 3} class="legend mid" class:sm={k.main.length > 3}>{k.main}</text>
          {/if}
        </g>
      {/each}
      {#if L.knob}
        {@const r = L.knob.w / 2 - 1}
        {@const cx = L.knob.x + L.knob.w / 2}
        {@const cy = L.knob.y + L.knob.h / 2}
        <circle {cx} {cy} {r} fill="#17121f" />
        <circle {cx} {cy} r={r - 3} fill="url(#knob)" stroke="#17121f" stroke-width="2" stroke-dasharray="2.5 3" />
        <circle {cx} {cy} r={r - 10} fill="#ff3ea5" stroke="#17121f" stroke-width="2" />
      {/if}
    </svg>
    <canvas class="layer tint" bind:this={tint}></canvas>

    <div class="layer hotspots">
      {#each L.keys as k (k.key)}
        {@const info = keys[k.key]}
        <button
          class="hot"
          class:changed={info?.changed}
          class:selected={editing && app.selectedKey === k.key}
          style:left={pct(k.x, L.width)} style:top={pct(k.y, L.height)}
          style:width={pct(k.w, L.width)} style:height={pct(k.h, L.height)}
          tabindex={editing ? 0 : -1}
          aria-label={`${keyLabel(k.key)}: ${describe(info?.action, app.state?.macros)}`}
          onclick={() => (app.selectedKey = k.key)}
          onpointerenter={() => (hover = k)}
          onpointerleave={() => (hover = null)}
          onfocus={() => (hover = k)}
          onblur={() => (hover = null)}
        ></button>
      {/each}
    </div>
    {#if editing && hover}
      {@const info = keys[hover.key]}
      <div class="tip" style:left={pct(hover.x + hover.w / 2, L.width)} style:top={pct(hover.y, L.height)}>
        <strong>{app.layer === "fn" ? "Fn + " : ""}{keyLabel(hover.key)}</strong>
        <span>{describe(info?.action, app.state.macros)}</span>
      </div>
    {/if}
  </div>
  {/if}
</div>

<style>
  .wrap { position: relative; display: grid; place-items: center; isolation: isolate; }
  .glow {
    position: absolute; z-index: -1; width: 92%; height: 100%; left: 4%; top: 8%;
    filter: blur(48px) saturate(1.6); opacity: .75; transition: opacity .4s;
  }
  .board { position: relative; user-select: none; filter: drop-shadow(8px 10px 0 #17121f); }
  .layer { position: absolute; inset: 0; width: 100%; height: 100%; }
  canvas.layer { pointer-events: none; }
  .under { filter: blur(3px) saturate(1.3); }
  .tint { mix-blend-mode: multiply; opacity: .55; transition: opacity .3s; }
  .editing .under, .editing .tint { opacity: .3; }
  .editing .glow { opacity: .25; }

  .cap .skirt { fill: #c9c0da; stroke: #17121f; stroke-width: 1.6; }
  .cap.accent .skirt { fill: color-mix(in oklab, var(--tab), #17121f 40%); }
  .legend { font: 750 15px "Bricolage Grotesque Variable", sans-serif; fill: #17121f; }
  .legend.sm { font-size: 11.5px; }
  .legend.mid { text-anchor: middle; dominant-baseline: middle; }
  .accent .legend { fill: #fff; }

  .hot {
    position: absolute; padding: 0; border: 0; background: transparent; border-radius: 7px;
    pointer-events: none; transition: background-color .12s, box-shadow .12s, transform .12s;
  }
  .editing .hot { pointer-events: auto; cursor: pointer; }
  .editing .hot:hover, .editing .hot:focus-visible {
    outline: none; transform: translateY(-2px);
    background: color-mix(in oklab, var(--color-sun) 45%, transparent); box-shadow: inset 0 0 0 3px #17121f;
  }
  .editing .hot.changed {
    background: color-mix(in oklab, var(--tab) 45%, transparent); box-shadow: inset 0 0 0 3px var(--tab);
  }
  .editing .hot.selected {
    background: color-mix(in oklab, var(--color-sun) 70%, transparent);
    box-shadow: inset 0 0 0 3px #17121f, 0 0 0 3px var(--color-sun), 0 0 0 6px #17121f, 0 0 26px var(--color-sun);
    transform: translateY(-2px);
  }
  .debug .hot { box-shadow: inset 0 0 0 1px #ff3df0; }

  .tip {
    position: absolute; transform: translate(-50%, calc(-100% - 12px)); pointer-events: none; z-index: 2;
    background: var(--color-sun); color: #17121f; border: 3px solid #17121f; border-radius: 12px; padding: .4rem .7rem;
    display: grid; font-size: .8rem; line-height: 1.35; white-space: nowrap; box-shadow: 3px 3px 0 #17121f;
  }
  .tip strong { font-weight: 800; }
  .tip span { color: rgb(23 18 31 / .7); font-weight: 600; }
</style>
