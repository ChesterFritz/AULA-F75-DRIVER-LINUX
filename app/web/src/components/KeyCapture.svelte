<script>
  // Click, then press a key or shortcut. value is a combo like "lctrl+c" (or one key when single).
  import { codeToName, MODS } from "../lib/labels.js";
  import { comboLabel } from "../lib/macro.js";

  let { value = $bindable(""), single = false, label = "Key", autofocus = false } = $props();
  let listening = $state(false);
  let el = $state();
  const held = new Set();

  $effect(() => { if (autofocus && el) el.focus(); });

  function keydown(e) {
    if (e.key === "Tab" && !held.size) return;
    e.preventDefault();
    e.stopPropagation();
    const n = codeToName(e.code);
    if (!n || e.repeat) return;
    if (single) { value = n; return; }
    if (!held.size) value = "";
    held.add(n);
    const mods = MODS.filter((m) => held.has(m));
    const rest = [...held].filter((x) => !MODS.includes(x)).slice(0, 2);
    value = [...mods, ...rest].join("+");
  }
  function keyup(e) { const n = codeToName(e.code); if (n) held.delete(n); }
</script>

<input bind:this={el} class="input cursor-pointer py-2 font-black caret-transparent {listening ? 'bg-sun/25' : ''}" readonly
       aria-label={label}
       style:box-shadow={listening ? "4px 4px 0 var(--tab)" : null}
       value={value ? comboLabel(value) : ""}
       placeholder={listening ? (single ? "Press a key…" : "Press keys now…") : "Click, then press keys"}
       onkeydown={keydown} onkeyup={keyup}
       onfocus={() => { held.clear(); listening = true; }}
       onblur={() => { held.clear(); listening = false; }}>
