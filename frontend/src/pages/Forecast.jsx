import { useEffect, useState } from "react";
import {
  ComposedChart, Area, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import { get, mw, hhmm } from "../api.js";

const fmt = (v) => (Array.isArray(v) ? `${mw(v[0])} to ${mw(v[1])}` : mw(v));

export default function Forecast() {
  const [date, setDate] = useState("2026-01-15");
  const [cutoff, setCutoff] = useState("09:00");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!date || !cutoff) return;
    setLoading(true);
    setError("");
    get("/api/forecast", { date, cutoff })
      .then(setData)
      .catch((e) => { setData(null); setError(e.message); })
      .finally(() => setLoading(false));
  }, [date, cutoff]);

  const pts = data
    ? data.points.map((p) => ({ ...p, time: hhmm(p.startTime), range: [p.lower, p.upper] }))
    : [];
  const avg = pts.length ? pts.reduce((s, p) => s + p.forecast, 0) / pts.length : null;
  const min = pts.length ? Math.min(...pts.map((p) => p.forecast)) : null;
  const max = pts.length ? Math.max(...pts.map((p) => p.forecast)) : null;
  const used = data ? data.publish_times_used : [];

  return (
    <section>
      <div className="controls">
        <label>Delivery day
          <input type="date" min="2026-01-01" max="2026-01-31" value={date} onChange={(e) => setDate(e.target.value)} />
        </label>
        <label>Decision cutoff on the day before (UK time)
          <input type="time" value={cutoff} onChange={(e) => setCutoff(e.target.value)} />
        </label>
      </div>

      {loading && <p className="note">Loading...</p>}
      {error && <p className="error">Could not load forecast: {error}</p>}

      {data && (
        <>
          <div className="cards">
            <div className="card"><span>Decision cutoff</span><b>{data.cutoff_local}</b><small>{data.cutoff_utc.replace("T", " ").replace("Z", " UTC")}</small></div>
            <div className="card"><span>Forecast version used</span><b>{used.length === 1 ? used[0].slice(0, 16).replace("T", " ") : `${used.length} versions`}</b><small>published (UTC), latest before cutoff</small></div>
            <div className="card"><span>Average forecast</span><b>{mw(avg)} MW</b><small>range {mw(min)} to {mw(max)} MW</small></div>
            <div className="card"><span>Historical P90 error</span><b>{mw(data.p90_abs_error)} MW</b><small>used for the shaded band</small></div>
          </div>

          <div className="panel">
            <h3>Wind forecast for {data.date}</h3>
            <p className="note">
              The line is the latest forecast you could act on at the cutoff. The shaded band is the forecast plus or minus
              the January 90th-percentile error: 9 times in 10 the real outcome was historically within this band.
              Actual generation is shown for comparison only (it was not known at decision time).
            </p>
            <ResponsiveContainer width="100%" height={380}>
              <ComposedChart data={pts} margin={{ top: 10, right: 20, left: 10, bottom: 10 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="time" />
                <YAxis tickFormatter={mw} label={{ value: "MW", angle: -90, position: "insideLeft" }} />
                <Tooltip formatter={fmt} />
                <Legend />
                <Area dataKey="range" name="Forecast +/- P90 error" stroke="none" fill="#2f80ed" fillOpacity={0.15} />
                <Line dataKey="forecast" name="Forecast" stroke="#2f80ed" strokeWidth={2.5} dot={false} />
                <Line dataKey="actual" name="Actual" stroke="#eb5757" strokeWidth={2} dot={false} strokeDasharray="5 4" />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </>
      )}
    </section>
  );
}
