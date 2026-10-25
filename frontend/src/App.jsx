import { useState } from "react";
import Forecast from "./pages/Forecast.jsx";
import Accuracy from "./pages/Accuracy.jsx";

export default function App() {
  const [tab, setTab] = useState("forecast");
  return (
    <div className="app">
      <header className="top">
        <div>
          <h1>Wind Forecast Portal</h1>
          <p className="sub">GB national wind generation: day-ahead buying support (January 2026, Elexon data)</p>
        </div>
        <nav>
          <button className={tab === "forecast" ? "tab active" : "tab"} onClick={() => setTab("forecast")}>
            Latest forecast
          </button>
          <button className={tab === "accuracy" ? "tab active" : "tab"} onClick={() => setTab("accuracy")}>
            Forecast accuracy
          </button>
        </nav>
      </header>
      <main>{tab === "forecast" ? <Forecast /> : <Accuracy />}</main>
      <footer>
        Data: Elexon BMRS (FUELHH actuals, WINDFOR forecasts). Error = actual minus forecast. Times in UTC (equal to UK time in January).
      </footer>
    </div>
  );
}
