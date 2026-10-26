import { useEffect, useState } from "react";
import {
  ComposedChart, Area, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import { get, mw, hhmm } from "../api.js";

const fmt = (v) => (Array.isArray(v) ? `${mw(v[0])} to ${mw(v[1])}` : mw(v));
const stamp = (iso) => iso.slice(0, 16).replace("T", " ");

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

  const band = data ? data.band : null;
  const pts = data
    ? data.points.map((p) => ({
        ...p,
        time: hhmm(p.startTime),
        range: band && band.available ? [p.lower, p.upper] : undefined,
      }))
    : [];
  const avg = pts.length ? pts.reduce((s, p) => s + p.forecast, 0) / pts.length : null;
  const used = data ? data.publish_times_used : [];

  return (
    <section>
      <div className="controls">
        <label>Delivery day (the day being bought for)
          <input type="date" min="2026-01-01" max="2026-01-31" value={date} onChange={(e) => setDate(e.target.value)} />
        </label>
        <label>Decision cutoff on the day before (UK time)
          <input type="time" value={cutoff} onChange={(e) => setCutoff(e.target.value)} />
        </label>
      </div>

      {loading && <p className="note">Updating...</p>}
      {error && <p className="error">Could not load forecast: {error}</p>}

      {data && (
        <div className={loading ? "stale" : ""}>
          <div className="cards">
            <div className="card"><span>Decision cutoff (D-1)</span><b>{data.cutoff_local} UK</b>
              <small>{stamp(data.cutoff_utc)} UTC (UK time = UTC in January)</small></div>
            <div className="card"><span>Forecast version used</span>
              <b>{used.length === 1 ? stamp(used[0]) + " UTC" : `${used.length} versions`}</b>
              <small>latest published at or before the cutoff</small></div>
            <div className="card"><span>Average forecast for the day</span><b>{mw(avg)} MW</b>
              <small>{data.hours_available} of 24 hours available{data.hours_missing > 0 ? `, ${data.hours_missing} missing` : ""}</small></div>
            <div className="card"><span>Uncertainty band (descriptive)</span>
              {band.available
                ? <><b>{mw(band.lo_err)} to +{mw(band.hi_err)} MW</b>
                    <small>5th to 95th percentile of past errors ({mw(band.history_slots)} earlier hours)</small></>
                : <><b>Not available</b><small>{band.method}</small></>}
            </div>
          </div>

          {data.hours_missing > 0 && (
            <p className="error">
              {data.hours_missing} hour(s) have no forecast published before this cutoff. They are left out, not filled in.
            </p>
          )}

          <div className="panel">
            <h3>Forecast available at the cutoff for {data.date}</h3>
            <p className="note">
              Blue line: the latest Elexon forecast published before the cutoff (a replay of history, not a live forecast).
              Shaded band: forecast plus the 5th to 95th percentile of the signed errors from earlier delivery days only
              (up to D-2). It is an empirical guide, not a guaranteed interval; its measured hit rate is on the Accuracy tab.
              Red dashed line: what actually happened, shown for comparison only (not known at decision time).
            </p>
            <ResponsiveContainer width="100%" height={380}>
              <ComposedChart data={pts} margin={{ top: 10, right: 20, left: 10, bottom: 10 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="time" label={{ value: "Hour (UTC = UK time in January)", position: "insideBottom", offset: -4 }} />
                <YAxis tickFormatter={mw} label={{ value: "MW", angle: -90, position: "insideLeft" }} />
                <Tooltip formatter={fmt} />
                <Legend verticalAlign="top" />
                {band.available && <Area dataKey="range" name="Forecast + past-error band" stroke="none" fill="#2f80ed" fillOpacity={0.15} />}
                <Line dataKey="forecast" name="Forecast" stroke="#2f80ed" strokeWidth={2.5} dot={false} />
                <Line dataKey="actual" name="Actual" stroke="#eb5757" strokeWidth={2} dot={false} strokeDasharray="5 4" />
              </ComposedChart>
            </ResponsiveContainer>
          </div>

          <div className="panel">
            <h3>Hour-by-hour evidence</h3>
            <p className="note">Every value behind the chart. Times are UTC, which equals UK local time in January. Error = actual minus forecast.</p>
            <div className="tablewrap">
              <table>
                <thead>
                  <tr><th>Hour (UTC)</th><th>Forecast MW</th><th>Actual MW</th><th>Error MW</th><th>Forecast published (UTC)</th><th>Lead time h</th></tr>
                </thead>
                <tbody>
                  {data.points.map((p) => (
                    <tr key={p.startTime}>
                      <td>{hhmm(p.startTime)}</td>
                      <td>{mw(p.forecast)}</td>
                      <td>{mw(p.actual)}</td>
                      <td className={p.err < 0 ? "neg" : ""}>{mw(p.err)}</td>
                      <td>{stamp(p.publishTime)}</td>
                      <td>{p.horizon_h}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
