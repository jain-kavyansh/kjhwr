import { useEffect, useState } from "react";
import Forecast from "./pages/Forecast.jsx";
import Accuracy from "./pages/Accuracy.jsx";
import About from "./pages/About.jsx";
import { get } from "./api.js";

const TABS = [
  ["forecast", "Decision-time forecast"],
  ["accuracy", "Forecast accuracy"],
  ["about", "Data and method"],
];

export default function App() {
  const [tab, setTab] = useState("forecast");
  const [snap, setSnap] = useState("");

  useEffect(() => {
    get("/api/data-quality", { cutoff: "09:00" })
      .then((d) => setSnap(d.snapshot && d.snapshot.retrieved_utc ? d.snapshot.retrieved_utc.replace("T", " ").replace("Z", " UTC") : ""))
      .catch(() => {});
  }, []);

  return (
    <div className="app">
      <header className="top">
        <div>
          <h1>Wind Forecast Evaluation Viewer</h1>
          <p className="sub">Day-ahead decision support: historical Elexon wind forecasts compared with actual generation (GB, national)</p>
        </div>
        <nav>
          {TABS.map(([k, label]) => (
            <button key={k} className={tab === k ? "tab active" : "tab"} onClick={() => setTab(k)}>{label}</button>
          ))}
        </nav>
      </header>

      <div className="banner">
        <b>Historical evaluation prototype, not a live forecast.</b> It replays the Elexon wind forecasts that were
        available before each day-ahead cutoff in <b>January 2026</b> and compares them with what actually happened.
        It does not estimate demand or recommend how much power to buy.
        <div className="banner-meta">
          Data period: 1 to 31 January 2026 (delivery days)
          {snap ? ` | Local data snapshot taken: ${snap}` : ""}
        </div>
      </div>

      <main>
        {tab === "forecast" && <Forecast />}
        {tab === "accuracy" && <Accuracy />}
        {tab === "about" && <About />}
      </main>
      <footer>
        Source: Elexon BMRS (FUELHH actuals, WINDFOR forecasts). Error = actual minus forecast. Times are UTC, which equals UK time in January.
      </footer>
    </div>
  );
}
