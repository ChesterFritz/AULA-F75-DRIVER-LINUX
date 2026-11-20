const TOKEN = new URLSearchParams(location.search).get("t") || "";

export async function api(path, body) {
  const opt = { headers: { "X-Token": TOKEN } };
  if (body !== undefined) {
    opt.method = "POST";
    opt.body = JSON.stringify(body);
    opt.headers["Content-Type"] = "application/json";
  }
  const r = await fetch("api/" + path, opt);
  if (r.status === 403) throw new Error("This window lost its link to the app. Close it and open AULA F75 again.");
  return r.json();
}

// Device writes run one at a time, in order.
let queue = Promise.resolve();
export function write(path, body) {
  const p = queue.then(() => api(path, body)).then((r) => {
    if (!r.ok) throw new Error(r.error || "Something went wrong.");
    return r;
  });
  queue = p.catch(() => {});
  return p;
}
