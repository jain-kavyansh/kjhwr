import { useEffect, useState } from "react";
import {
  BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ReferenceLine,
} from "recharts";
import { get, mw } from "../api.js";

function Card({ label, value, unit, hint }) {
  return (
    <div className="card">
      <span>{label}</span>
      <b>{value}{unit ? ` ${unit}` : ""}</b>
      <small>{hint}</small>
    </div>
  );
}

export default function Accuracy() {
  const [start, setStart] = useState("2026-01-01");
  const [end, setEnd] = useState("2026-01-31");
  const [cutoff, setCutoff] = useState("09:00");
  const [m, setM] = useState(null);
  const [hour, setHour] = useState([]);
  const [day, setDay] = useState([]);
  const [horizon, setHorizon] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!start || !end || !cutoff) return;
    if (start > end) { setError("Start date must be on or before the end date."); return; }
    setLoading(true);
    setError("");
    const p = { start, end, cutoff };
    Promise.all([
      get("/api/metrics", p),
      get("/api/error-breakdown", { ...p, by: "hour" }),
      get("/api/error-breakdown", { ...p, by: "day" }),
      get("/api/error-breakdown", { ...p, by: "horizon" }),
    ])
      .then(([a, b, c, d]) => {
        setM(a.metrics); setHour(b.rows); setDay(c.rows); setHorizon(d.rows);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [start, end, cutoff]);

  const ok = m && m.n > 0;

  return (
    <section>
      <div className="controls">
        <label>From (delivery day)<input type="date" min="2026-01-01" max="2026-01-31" value={start} onChange={(e) => setStart(e.target.value)} /></label>
        <label>To<input type="date" min="2026-01-01" max="2026-01-31" value={end} onChange={(e) => setEnd(e.target.value)} /></label>
        <label>Decision cutoff (UK time)<input type="time" value={cutoff} onChange={(e) => setCutoff(e.target.value)} /></label>
      </div>

      {loading && <p className="note">Loading...</p>}
      {error && <p className="error">Could not load accuracy data: {error}</p>}

      {ok && (
        <>
          <div className="cards">
            <Card label="Mean absolute error" value={mw(m.mae)} unit="MW" hint={`${m.nmae_pct}% of mean output (${mw(m.mean_actual)} MW)`} />
            <Card label="RMSE" value={mw(m.rmse)} unit="MW" hint="penalises large misses" />
            <Card label="Bias (actual - forecast)" value={mw(m.bias)} unit="MW" hint={m.bias < 0 ? "forecast too HIGH on average: risk of under-buying" : "forecast too LOW on average"} />
            <Card label="90% of misses below" value={mw(m.abs_error_p90)} unit="MW" hint={`median ${mw(m.abs_error_p50)}, P95 ${mw(m.abs_error_p95)}`} />
          </div>
          <p className="note">Based on {m.n} hourly slots. Each slot uses the latest forecast published before the cutoff.</p>

          <div className="panel">
            <h3>Error by day</h3>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={day} margin={{ top: 10, right: 20, left: 10, bottom: 10 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" tickFormatter={(d) => d.slice(8)} />
                <YAxis tickFormatter={mw} label={{ value: "MW", angle: -90, position: "insideLeft" }} />
                <Tooltip formatter={mw} />
                <Legend />
                <ReferenceLine y={0} stroke="#999" />
                <Line dataKey="mae" name="MAE" stroke="#2f80ed" strokeWidth={2} />
                <Line dataKey="bias" name="Bias" stroke="#eb5757" strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="panel">
            <h3>Error by hour of day</h3>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={hour} margin={{ top: 10, right: 20, left: 10, bottom: 10 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="hour" tickFormatter={(h) => `${String(h).padStart(2, "0")}:00`} />
                <YAxis tickFormatter={mw} />
                <Tooltip formatter={mw} />
                <Legend />
                <Bar dataKey="mae" name="MAE" fill="#2f80ed" />
                <Bar dataKey="p90" name="P90 abs. error" fill="#9bb8e8" />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="panel">
            <h3>Error by forecast lead time</h3>
            <p className="note">Uses every forecast version, not only the one chosen at the cutoff, to show how accuracy changes with how far ahead the forecast was made.</p>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={horizon} margin={{ top: 10, right: 20, left: 10, bottom: 10 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="label" />
                <YAxis tickFormatter={mw} />
                <Tooltip formatter={mw} />
                <Legend />
                <Bar dataKey="mae" name="MAE" fill="#2f80ed" />
                <Bar dataKey="rmse" name="RMSE" fill="#9bb8e8" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </>
      )}
      {m && m.n === 0 && !error && <p className="note">No data for this selection.</p>}
    </section>
  );
}
