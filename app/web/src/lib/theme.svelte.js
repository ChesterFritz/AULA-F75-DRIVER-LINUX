// Light / dark / system theme, remembered per browser profile.
const KEY = "aula-f75-theme";
const media = matchMedia("(prefers-color-scheme: dark)");
const reduce = matchMedia("(prefers-reduced-motion: reduce)");

function stored() {
  try { return localStorage.getItem(KEY) || "system"; } catch { return "system"; }
}

export const theme = $state({ choice: stored() });

export function resolved() {
  return theme.choice === "system" ? (media.matches ? "dark" : "light") : theme.choice;
}

/**
 * Switch with a GPU snapshot (View Transitions) instead of transitioning every element's
 * colours: the new theme grows as a circle from the point that was clicked.
 */
function apply(origin) {
  const root = document.documentElement;
  const next = resolved();
  if (root.dataset.theme === next) return;
  if (!document.startViewTransition || reduce.matches || document.hidden) {
    root.dataset.theme = next;
    return;
  }
  const x = origin?.x ?? innerWidth / 2, y = origin?.y ?? innerHeight / 2;
  const r = Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y));
  const t = document.startViewTransition(() => { root.dataset.theme = next; });
  t.ready.then(() => {
    root.animate(
      { clipPath: [`circle(0px at ${x}px ${y}px)`, `circle(${r}px at ${x}px ${y}px)`] },
      { duration: 480, easing: "cubic-bezier(.3, .7, .2, 1)", pseudoElement: "::view-transition-new(root)" },
    );
  }).catch(() => {});
}

export function setTheme(choice, event) {
  theme.choice = choice;
  try { localStorage.setItem(KEY, choice); } catch {}
  const b = event?.currentTarget?.getBoundingClientRect();
  apply(b ? { x: b.left + b.width / 2, y: b.top + b.height / 2 } : null);
}

media.addEventListener("change", () => { if (theme.choice === "system") apply(); });
document.documentElement.dataset.theme = resolved();
