// Approximate, per-key preview of the keyboard's built-in lighting effects.
const TAU = Math.PI * 2;

export function hsv(h, s = 1, v = 1) {
  h = ((h % 1) + 1) % 1;
  const i = Math.floor(h * 6), f = h * 6 - i;
  const p = v * (1 - s), q = v * (1 - f * s), u = v * (1 - (1 - f) * s);
  const [r, g, b] = [[v, u, p], [q, v, p], [p, v, u], [p, q, v], [u, p, v], [v, p, q]][i % 6];
  return [(r * 255) | 0, (g * 255) | 0, (b * 255) | 0];
}

export const hexToRgb = (h) => [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16));

export function createSim(keys, W, H) {
  const n = keys.length;
  const K = keys.map((k, i) => ({ ...k, i, nx: (k.x + k.w / 2) / W, ny: (k.y + k.h / 2) / H }));
  const index = Object.fromEntries(K.map((k) => [k.key, k.i]));
  const energy = new Float32Array(n);
  const hue = new Float32Array(n);
  const out = K.map(() => [0, 0, 0, 0]);
  let ripples = [];
  let spawn = 0, flash = 0, idle = 0;

  // serpentine path through the rows, for the snake
  const rows = {};
  K.forEach((k) => (rows[Math.round(k.ny * 6)] ||= []).push(k));
  const path = Object.keys(rows).map(Number).sort((a, b) => a - b)
    .flatMap((r, ri) => rows[r].sort((a, b) => (ri % 2 ? b.nx - a.nx : a.nx - b.nx)).map((k) => k.i));

  const aspect = H / W;
  const dist = (k, x, y) => Math.hypot(k.nx - x, (k.ny - y) * aspect);

  function poke(name) {
    const i = index[name];
    if (i === undefined) return;
    energy[i] = 1;
    hue[i] = Math.random();
    idle = 0;
    ripples.push({ x: K[i].nx, y: K[i].ny, r: 0, h: Math.random() });
    if (ripples.length > 24) ripples.shift();
  }
  function pop(rate, dt) {
    const c = rate * dt;
    const count = Math.floor(c) + (Math.random() < c % 1 ? 1 : 0);
    for (let j = 0; j < count; j++) {
      const i = (Math.random() * n) | 0;
      energy[i] = 1;
      hue[i] = Math.random();
    }
  }
  const decay = (rate, dt) => { for (let i = 0; i < n; i++) energy[i] = Math.max(0, energy[i] - dt * rate); };

  function frame(name, base, speed, t, dt, pointer) {
    const sp = 0.35 + speed * 0.4;
    const T = t * sp;
    idle += dt;
    const col = (i, h) => base || hsv(h ?? K[i].nx * 0.9 + T * 0.05);
    const set = (i, rgb, a) => { const o = out[i]; o[0] = rgb[0]; o[1] = rgb[1]; o[2] = rgb[2]; o[3] = a; };

    switch (name) {
      case "respire": {
        const a = 0.08 + 0.92 * (0.5 - 0.5 * Math.cos(T * 2.2));
        K.forEach((k) => set(k.i, col(k.i), a));
        break;
      }
      case "rainbow":
        K.forEach((k) => set(k.i, hsv(k.nx * 0.9 - T * 0.25), 1));
        break;
      case "flash-away":
        pop(14 * sp, dt); decay(1.6 * sp, dt);
        K.forEach((k) => set(k.i, col(k.i, hue[k.i]), energy[k.i]));
        break;
      case "raindrops":
        pop(9 * sp, dt); decay(0.9 * sp, dt);
        K.forEach((k) => set(k.i, col(k.i, hue[k.i]), energy[k.i] ** 1.5));
        break;
      case "rainbow-wheel":
        K.forEach((k) => set(k.i, hsv(Math.atan2((k.ny - 0.5) * aspect, k.nx - 0.5) / TAU + T * 0.2), 1));
        break;
      case "ripples":
      case "reaction": {
        spawn -= dt;
        if (spawn <= 0 && idle > 1.5) {
          spawn = 1.3 / sp;
          const k = K[(Math.random() * n) | 0];
          ripples.push({ x: k.nx, y: k.ny, r: 0, h: Math.random() });
        }
        if (name === "reaction") {
          decay(1.3 * sp, dt);
          K.forEach((k) => set(k.i, col(k.i, hue[k.i]), Math.max(energy[k.i], 0.06)));
          ripples = [];
          if (idle > 1.5) pop(2 * sp, dt);
          break;
        }
        ripples.forEach((r) => (r.r += dt * 0.42 * sp));
        ripples = ripples.filter((r) => r.r < 1.1);
        K.forEach((k) => {
          let a = 0, h = 0;
          for (const r of ripples) {
            const v = Math.exp(-(((dist(k, r.x, r.y) - r.r) / 0.03) ** 2)) * (1 - r.r / 1.1);
            if (v > a) { a = v; h = r.h; }
          }
          set(k.i, col(k.i, h), a);
        });
        break;
      }
      case "stars":
        pop(6 * sp, dt); decay(0.55 * sp, dt);
        K.forEach((k) => set(k.i, col(k.i, hue[k.i]), Math.sin(energy[k.i] * Math.PI)));
        break;
      case "shadow": {
        const p = pointer && idle > 0.2 ? pointer : idle > 2
          ? { x: 0.5 + 0.42 * Math.sin(T * 0.9), y: 0.5 + 0.35 * Math.sin(T * 1.7) } : null;
        if (p) K.forEach((k) => { energy[k.i] = Math.max(energy[k.i], Math.exp(-(dist(k, p.x, p.y) ** 2) / 0.0015)); });
        decay(1.1 * sp, dt);
        K.forEach((k) => set(k.i, col(k.i, T * 0.1), energy[k.i]));
        break;
      }
      case "snake": {
        const head = Math.floor(T * 14);
        K.forEach((k) => set(k.i, [0, 0, 0], 0));
        for (let j = 0; j < 10; j++) {
          const i = path[(((head - j) % path.length) + path.length) % path.length];
          set(i, col(i, (head - j) / 40), 1 - j / 10);
        }
        break;
      }
      case "neon": {
        const a = base ? 0.55 + 0.45 * Math.sin(T * 2) : 1;
        K.forEach((k) => set(k.i, base || hsv(T * 0.12), a));
        break;
      }
      case "sine-wave":
        K.forEach((k) => set(k.i, col(k.i), 0.5 + 0.5 * Math.sin(k.nx * 14 - T * 3)));
        break;
      case "scan": {
        const p = 0.5 + 0.55 * Math.sin(T * 1.2);
        K.forEach((k) => set(k.i, col(k.i), Math.exp(-(((k.nx - p) / 0.07) ** 2))));
        break;
      }
      case "windmill":
        K.forEach((k) => {
          const ang = Math.atan2((k.ny - 0.5) * aspect, k.nx - 0.5);
          set(k.i, hsv(ang / TAU + T * 0.15), 0.3 + 0.7 * (0.5 + 0.5 * Math.cos(4 * ang - T * 2.5)));
        });
        break;
      case "waterfall":
        K.forEach((k) => set(k.i, hsv(k.ny * 0.7 - T * 0.3), 1));
        break;
      case "blossom":
        K.forEach((k) => set(k.i, hsv(dist(k, 0.5, 0.5) * 1.6 - T * 0.25), 1));
        break;
      case "storm": {
        if (Math.random() < dt * 0.45 * sp) flash = 1;
        flash = Math.max(0, flash - dt * 3);
        pop(8 * sp, dt); decay(2 * sp, dt);
        K.forEach((k) => {
          const a = Math.max(energy[k.i], flash);
          set(k.i, flash > energy[k.i] ? [235, 240, 255] : col(k.i, hue[k.i]), a);
        });
        break;
      }
      default: // fixed
        K.forEach((k) => set(k.i, col(k.i), 1));
    }
    return out;
  }

  return { frame, poke, keys: K };
}
