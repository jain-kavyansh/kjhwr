import { useEffect, useState } from "react";
import { get, mw } from "../api.js";

const Row = ({ k, v }) => (<tr><td>{k}</td><td>{v}</td></tr>);

export default function About() {
  const [q, setQ] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    get("/api/data-quality", { cutoff: "09:00" }).then(setQ).catch((e) => setError(e.message));
  }, []);

  const s = q && q.snapshot ? q.snapshot : {};

  return (
    <section>
      {error && <p className="error">Could not load data details: {error}</p>}

      <div className="panel">
        <h3>What this app does and does not do</h3>
        <ul className="list">
          <li><b>Does:</b> shows the latest Elexon wind forecast that was available before a chosen day-ahead cutoff, and measures how far those forecasts were from actual generation in January 2026.</li>
          <li><b>Does not:</b> produce its own forecast, show live data, estimate demand, or recommend how much power to buy.</li>
          <li><b>Evidence:</b> one month (744 hourly pairs). Treat the results as indicative, not as a stable long-run estimate.</li>
        </ul>
      </div>

      <div className="panel">
        <h3>Data provenance</h3>
        <div className="tablewrap"><table><tbody>
          <Row k="Source" v={s.source || "Elexon BMRS open data API"} />
          <Row k="Local snapshot taken" v={s.retrieved_utc ? s.retrieved_utc.replace("T", " ").replace("Z", " UTC") : "-"} />
          <Row k="Actuals" v={s.actuals ? `${s.actuals.dataset}, fuel type ${s.actuals.fuelType}, ${s.actuals.unit}, ${s.actuals.resolution}, settlement dates ${s.actuals.settlement_dates}` : "-"} />
          <Row k="Forecasts" v={s.forecasts ? `${s.forecasts.dataset}, ${s.forecasts.unit}, ${s.forecasts.resolution}, published ${s.forecasts.publish_window_utc}` : "-"} />
          <Row k="Time zone" v="Stored in UTC. UK local time equals UTC in January (GMT)." />
          <Row k="Comparison grid" v="Forecasts are hourly and actuals half-hourly, so only on-the-hour actuals are compared." />
        </tbody></table></div>
      </div>

      {q && (
        <div className="panel">
          <h3>Data quality checks (cutoff {q.cutoff})</h3>
          <div className="tablewrap"><table><tbody>
            <Row k="Actual rows / expected half-hours" v={`${mw(q.actual_rows)} / ${mw(q.actual_expected_half_hours)}`} />
            <Row k="Missing actual half-hours" v={q.actual_missing_half_hours} />
            <Row k="Duplicate actual slots" v={q.actual_duplicate_slots} />
            <Row k="Forecast rows / forecast publications" v={`${mw(q.forecast_rows)} / ${q.forecast_publications}`} />
            <Row k="Duplicate forecast rows" v={q.forecast_duplicate_rows} />
            <Row k="Forecast rows dropped (target time not after publish time)" v={mw(q.forecast_rows_dropped_target_not_after_publish)} />
            <Row k="Hours with a forecast before the cutoff / expected" v={`${q.hours_with_forecast} / ${q.expected_hourly_slots}`} />
            <Row k="Hours missing a forecast (left out, not filled in)" v={q.hours_missing_forecast} />
            <Row k="Forecast and actual pairs used" v={q.pairs_used} />
            <Row k="Pairs excluded because no actual exists" v={q.pairs_excluded_no_actual} />
          </tbody></table></div>
        </div>
      )}

      <div className="panel">
        <h3>How the cutoff works</h3>
        <ul className="list">
          <li>Delivery day D is bought on day D-1. The cutoff is a time on D-1 in UK local time, converted to UTC.</li>
          <li>For each hour of D, the app keeps forecasts published at or before the cutoff and takes the most recent one.</li>
          <li>If none was published before the cutoff, that hour is reported as missing and excluded. Nothing is filled in.</li>
          <li>The default 09:00 is an assumption, not the exact exchange gate closure. You can change it.</li>
        </ul>
      </div>

      <div className="panel">
        <h3>Plain-language glossary</h3>
        <ul className="list">
          <li><b>Error:</b> actual minus forecast, in MW.</li>
          <li><b>MAE:</b> the average size of the miss, ignoring direction.</li>
          <li><b>RMSE:</b> like MAE but large misses count more.</li>
          <li><b>Bias:</b> the average signed error. Negative means actual wind came in below the forecast, so a buyer relying on the forecast would tend to under-buy and face a shortfall.</li>
          <li><b>90% of misses below (P90):</b> in 9 of 10 hours the absolute miss was smaller than this.</li>
          <li><b>Uncertainty band:</b> forecast plus the 5th to 95th percentile of earlier days' signed errors. Descriptive, with its measured hit rate shown on the Accuracy tab.</li>
        </ul>
      </div>
    </section>
  );
}
