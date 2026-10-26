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
  const [cov, setCov] = useState(null);
  const [halves, setHalves] = useState([]);
  const [shown, setShown] = useState("");
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
      get("/api/band-coverage", { cutoff }),
      get("/api/metrics", { start: "2026-01-01", end: "2026-01-15", cutoff }),
      get("/api/metrics", { start: "2026-01-16", end: "2026-01-31", cutoff }),
    ])
      .then(([a, b, c, d, e, h1, h2]) => {
        setM(a.metrics); setHour(b.rows); setDay(c.rows); setHorizon(d.rows); setCov(e);
        setHalves([["1 to 15 Jan", h1.metrics], ["16 to 31 Jan", h2.metrics]]);
        setShown(`${start} to ${end}, cutoff ${cutoff}`);
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

      {loading && <p className="note">Updating... the figures below are still the previous selection until this finishes.</p>}
      {error && <p className="error">Could not load accuracy data: {error}</p>}

      {ok && (
        <div className={loading ? "stale" : ""}>
          <p className="note">Showing: delivery days {shown}. Sample size: {m.n} hourly forecast and actual pairs.</p>
          <div className="cards">
            <Card label="Mean absolute error (MAE)" value={mw(m.mae)} unit="MW" hint={`${m.nmae_pct}% of mean output (${mw(m.mean_actual)} MW)`} />
            <Card label="RMSE" value={mw(m.rmse)} unit="MW" hint="penalises large misses more" />
            <Card label="Bias (actual - forecast)" value={mw(m.bias)} unit="MW" hint={m.bias < 0 ? "forecast too HIGH on average: risk of under-buying" : "forecast too LOW on average"} />
            <Card label="90% of misses below" value={mw(m.abs_error_p90)} unit="MW" hint={`median ${mw(m.abs_error_p50)}, P95 ${mw(m.abs_error_p95)}`} />
          </div>

          {cov && (
            <div className="panel">
              <h3>How reliable is the uncertainty band?</h3>
              <p className="note">
                The band for each day is built only from earlier days' errors, then checked against what happened. Aimed at 90%.
                Measured: <b>{cov.coverage_pct}%</b> of {mw(cov.slots)} hours fell inside the band, over {cov.days_with_band} days
                (the first days have no band because at least {cov.min_history_days} earlier days are needed).
                With a single month this is indicative only.
              </p>
            </div>
          )}

          <div className="panel">
            <h3>Is the result stable within January?</h3>
            <div className="tablewrap">
              <table>
                <thead><tr><th>Delivery days</th><th>Hours</th><th>MAE MW</th><th>RMSE MW</th><th>Bias MW</th><th>90% of misses below MW</th></tr></thead>
                <tbody>
                  {halves.map(([label, x]) => (
                    <tr key={label}><td>{label}</td><td>{x.n}</td><td>{mw(x.mae)}</td><td>{mw(x.rmse)}</td><td>{mw(x.bias)}</td><td>{mw(x.abs_error_p90)}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

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
            <h3>Error by hour of day (UTC = UK time in January)</h3>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={hour} margin={{ top: 10, right: 20, left: 10, bottom: 10 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="hour" tickFormatter={(h) => `${String(h).padStart(2, "0")}:00`} />
                <YAxis tickFormatter={mw} />
                <Tooltip formatter={mw} />
                <Legend />
                <Bar dataKey="mae" name="MAE" fill="#2f80ed" />
                <Bar dataKey="p90" name="90% of misses below" fill="#9bb8e8" />
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
        </div>
      )}
      {m && m.n === 0 && !error && <p className="note">No data for this selection.</p>}
    </section>
  );
}
