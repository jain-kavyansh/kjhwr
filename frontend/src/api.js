// Empty base = same origin (dev proxy). In production set VITE_API_URL.
const BASE = import.meta.env.VITE_API_URL || "";

export async function get(path, params = {}) {
  const q = new URLSearchParams(params);
  const res = await fetch(`${BASE}${path}?${q}`);
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const j = await res.json();
      msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
    } catch (e) {
      /* ignore */
    }
    throw new Error(msg);
  }
  return res.json();
}

export const mw = (v) =>
  v === null || v === undefined ? "-" : Math.round(v).toLocaleString("en-GB");
export const hhmm = (iso) => iso.slice(11, 16);
